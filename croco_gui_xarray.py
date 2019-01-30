# -*- coding: UTF-8 -*-
#

import sys
import os
from   shutil import copyfile
import wx
import time
from datetime import datetime
import xarray as xr
import numpy as np
from numpy.matlib import repmat
import numpy.ma as ma
import scipy.io
import netCDF4 as netcdf
import matplotlib.pyplot as plt
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar
import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib import colors
from matplotlib import animation
# from matplotlib.widgets  import RectangleSelector
from CrocoXarray import Croco
from derived_variables import get_pv, get_zetak, get_dtdz
from myplot import plotCurv, mypcolor

wildcard = "Netcdf Files (*.nc)|*.nc"
figsize = [6,5]


########################################################################

class SectionFrame(wx.Frame):
    """ 
    Window class to plot longitude and latitude sections.
    The window contains a canvas to plot, several buttons (animation, zoom in, zoom out, 
    print and reset color) and text control (start time and end time for animation, 
    min and max color for the colorbar)

    Attributes:
    croco : croco instance to study
    variableName : Name of the variable to plot in the canvas
    variable : 3D dataarray (x,y,t) of the variable to plot
    x : numpy array of x coordinates
    y : numpy array of y coordinates
    typSection: type of slice XZ or YZ
    sliceCoord: coordinate of the slice (latitude for XZ, latitude for YZ)
    timeIndex: current time index to plot
    """

    def __init__(self, croco=None, variableName = None, variable=None, x=None, y=None, \
        typSection=None , sliceCoord = None, timeIndex=None):
        """ return a SectioFrame instance """

        # Create the window
        wx.Frame.__init__(self, None, wx.ID_ANY, title='Section')

        # Now create the Panel to put the other controls on.
        self.panel = wx.Panel(self, wx.ID_ANY)

        # and a few controls
        self.figure = Figure()
        self.axes = self.figure.add_axes([0,0,1,1])
        self.canvas = FigureCanvas(self.panel, -1, self.figure)       
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Hide()

        self.TimeLabel = wx.StaticText(self.panel,-1,label="Time",style = wx.ALIGN_CENTER)
        self.TimeTxt = wx.TextCtrl(self.panel, wx.ID_ANY, " ", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)
        self.ZoomBtn = wx.Button(self.panel, wx.ID_ANY, "Zoom")
        self.PanBtn = wx.Button(self.panel, wx.ID_ANY, "Pan")
        self.HomeBtn = wx.Button(self.panel, wx.ID_ANY, "Home")
        self.SaveBtn = wx.Button(self.panel, wx.ID_ANY, "Save")

        self.AnimationBtn = wx.Button(self.panel, wx.ID_ANY, "Animation")
        self.startTimeTxt = wx.TextCtrl(self.panel, wx.ID_ANY, "1", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)
        self.endTimeTxt = wx.TextCtrl(self.panel, wx.ID_ANY, "1", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)
        self.CancelBtn = wx.Button(self.panel, wx.ID_ANY, "Cancel")
        self.SaveBtn = wx.Button(self.panel, wx.ID_ANY, "Save")
        
        self.ResetColorBtn = wx.Button(self.panel, wx.ID_ANY, "Reset Color")
        self.MinColorTxt = wx.TextCtrl(self.panel, wx.ID_ANY, "Min Color", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)
        self.MaxColorTxt = wx.TextCtrl(self.panel, wx.ID_ANY, "Max Color", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)

        # bind the menu event to an event handler
        self.canvas.mpl_connect('button_press_event', self.onFigureClick)
        self.canvas.mpl_connect('<Escape>', self.abortAnim)
        self.AnimationBtn.Bind(wx.EVT_BUTTON, self.onAnimationBtn)
        self.startTimeTxt.Bind(wx.EVT_TEXT_ENTER, self.onstartTimeTxt)
        self.endTimeTxt.Bind(wx.EVT_TEXT_ENTER, self.onendTimeTxt)
        self.ZoomBtn.Bind(wx.EVT_BUTTON, self.onZoomBtn)
        self.PanBtn.Bind(wx.EVT_BUTTON, self.onPanBtn)
        self.HomeBtn.Bind(wx.EVT_BUTTON, self.onHomeBtn)
        self.SaveBtn.Bind(wx.EVT_BUTTON, self.onSaveBtn)
        self.ResetColorBtn.Bind(wx.EVT_BUTTON, self.onResetColorBtn)
        self.MinColorTxt.Bind(wx.EVT_TEXT_ENTER, self.onMinColorTxt)
        self.MaxColorTxt.Bind(wx.EVT_TEXT_ENTER, self.onMaxColorTxt)
        self.CancelBtn.Bind(wx.EVT_BUTTON, self.onCancelBtn)
        self.SaveBtn.Bind(wx.EVT_BUTTON, self.onSaveBtn)
        self.TimeTxt.Bind(wx.EVT_TEXT_ENTER, self.onTimeTxt)

        self.showPosition = self.CreateStatusBar(2)
        self.showPosition.SetStatusText("x=	  , y=  ",1)
        self.showPosition.SetStatusWidths([-1,150])

        self.__do_layout()

        # Initialize the variables of the class
        self.croco = croco
        self.variable = variable
        self.x = x
        self.y = y
        self.variableName = variableName
        self.typSection = typSection
        self.sliceCoord = sliceCoord
        self.timeIndex = timeIndex
        if croco is not None:
            self.time = self.croco.wrapper._get_date(0)
            self.TimeTxt.SetValue(str(self.time))
        if typSection == "XZ":
            self.xlabel = "Longitude"
            self.ylabel = "Depth"
            self.slice = "Latitude"
        elif typSection == "YZ":
            self.xlabel = "Latitude"
            self.ylabel = "Depth"
            self.slice = "Longitude"
        if croco is not None:
            timeMin = self.croco.wrapper._get_date(0)
            timeMax = self.croco.wrapper._get_date(self.croco.wrapper.ntimes-1)
            self.startTimeTxt.SetValue(str(timeMin))
            self.startTime = timeMin
            self.startTimeIndex = 0
            self.endTimeTxt.SetValue(str(timeMax))
            self.endTime = timeMax
            self.endTimeIndex = self.croco.wrapper.ntimes -1

    def __do_layout(self):
        """
        Use a sizer to layout the controls, stacked vertically or horizontally
        """
        topSizer        = wx.BoxSizer(wx.VERTICAL)
        canvasSizer     = wx.BoxSizer(wx.VERTICAL)
        timeSizer       = wx.BoxSizer(wx.HORIZONTAL)
        buttonsSizer    = wx.BoxSizer(wx.HORIZONTAL)
        colorSizer      = wx.BoxSizer(wx.HORIZONTAL)

        canvasSizer.Add(self.canvas, 0, wx.ALL, 5)

        timeSizer.Add(self.TimeLabel,0, wx.ALL, 5)
        timeSizer.Add(self.TimeTxt,0, wx.ALL, 5)
        timeSizer.Add(self.ZoomBtn,0, wx.ALL, 5)
        timeSizer.Add(self.PanBtn,0, wx.ALL, 5)
        timeSizer.Add(self.HomeBtn,0, wx.ALL, 5)
        timeSizer.Add(self.SaveBtn,0, wx.ALL, 5)

        buttonsSizer.Add(self.AnimationBtn,0, wx.ALL, 5)
        buttonsSizer.Add(self.startTimeTxt,0, wx.ALL, 5)
        buttonsSizer.Add(self.endTimeTxt,0, wx.ALL, 5)
        buttonsSizer.Add(self.CancelBtn,0, wx.ALL, 5)
        buttonsSizer.Add(self.SaveBtn,0, wx.ALL, 5)

        colorSizer.Add(self.ResetColorBtn, 0, wx.ALL, 5)
        colorSizer.Add(self.MinColorTxt, 0, wx.ALL, 5)
        colorSizer.Add(self.MaxColorTxt, 0, wx.ALL, 5)

        topSizer.Add(canvasSizer, 0, wx.CENTER)
        topSizer.Add(timeSizer, 0, wx.ALL|wx.EXPAND, 5)
        topSizer.Add(buttonsSizer, 0, wx.ALL|wx.EXPAND, 5)
        topSizer.Add(colorSizer, 0, wx.ALL|wx.EXPAND, 5)

        self.panel.SetSizer(topSizer)
        topSizer.Fit(self)

        self.Layout()


    # ------------ Event handler

    # Event handler on plot canvas
    def onFigureClick(self,event):
        """Event handler for the button click on plot"""
        self.xPress, self.yPress = event.xdata, event.ydata

    def ShowPosition(self, event):
        if event.inaxes:
            self.showPosition.SetStatusText(
                "x={:5.1f}  y={:5.1f}".format(event.xdata, event.ydata),1)

    def rect_select_callback(self, eclick, erelease):
        """Event handler for rectangle selector on plot"""
        self.xPress, self.yPress = eclick.xdata, eclick.ydata
        self.xRelease, self.yRelease = erelease.xdata, erelease.ydata
        self.xlim = [min(self.xPress,self.xRelease),max(self.xPress,self.xRelease)]
        self.ylim = [ min(self.yPress,self.yRelease),max(self.yPress,self.yRelease)]
        self.drawz(setlim=False)


    def onCancelBtn(self,event):
    	# global abort_anim
    	abort_anim=True
    	print("Not implemented yet")

    def abortAnim(self,event):
    	# global abort_anim
		self.anim.event_source.stop()

    # Event handler for animation
    def onAnimationBtn(self,event):
	    # abort_anim = False

		# def onClick(event):
		# 	# nonlocal abort_anim
		# 	# if abort_anim:
		# 	self.anim.event_source.stop()
		# 	# abort_anim = False

		"""Event handler for the button click Animation button"""
		printDir = self.croco.startDir+"/Figures_" + self.croco.get_run_name()+"/"
		if not os.path.isdir(printDir):
		        os.mkdir(printDir)
		os.system('rm -rf '+printDir+'dummy.mp4')
		# self.clim = [np.min(self.variable),np.max(self.variable)]
		save_count = self.endTimeIndex - self.startTimeIndex + 1
		self.anim = animation.FuncAnimation(self.figure, self.animate, \
		           frames = range(self.startTimeIndex,self.endTimeIndex+1), repeat=False, \
		           blit = False, save_count=save_count)
		mpl.verbose.set_level("helpful")
		self.anim.save(printDir+'dummy.mp4')
		# self.canvas.draw()

    # Event handler for Save animation
    def onSaveBtn(self,event): 
        """Event handler for the button click Animation button"""
        os.system('rm -rf ./Figures/'+self.variableName+'.mp4')
        try:
            os.makedirs('./Figures')
        except:
            pass 
        time1 = str(self.croco.wrapper._get_date(self.startTimeIndex))
        time2 = str(self.croco.wrapper._get_date(self.endTimeIndex))
        filename = "{:s}_{:s}{:4.1f}_Time{:s}-{:s}.mp4".format(self.variableName,self.slice,self.sliceCoord, \
            time1,time2).replace(" ", "") 
        copyfile(printDir+'dummy.mp4',printDir+filename )

    def animate( self, i):
        """ Function to plot animation in canvas """
        # global abort_anim
        self.timeIndex = i
        # if abort_anim:
        # 	self.anim.event_source.stop()
        # 	abort_anim = False
        # else:
        # 	self.updateVariableZ(setlim=False)
        self.updateVariableZ(setlim=False)

    def onstartTimeTxt(self,event):
        """Event handler for Enter key in start time text """
        self.startTime = float(self.startTimeTxt.GetValue())
        times = self.croco.wrapper.coords['time'].values
        # find nearest index corresponding to instant time to plot
        self.startTimeIndex = min( range( len(times) ), \
            key=lambda j:abs(self.startTime-times[j]))
        self.startTime = self.croco.wrapper._get_date(self.startTimeIndex)
        self.startTimeTxt.SetValue(str(self.startTime))

    # Event handler for Time dialog
    def onendTimeTxt(self,event):
        """Event handler for Enter key in end time text """
        self.endTime = float(self.endTimeTxt.GetValue())
        times = self.croco.wrapper.coords['time'].values
        # find nearest index corresponding to instant time to plot
        self.endTimeIndex = min( range( len(times) ), \
            key=lambda j:abs(self.endTime-times[j]))
        self.endTime = self.croco.wrapper._get_date(self.endTimeIndex)
        self.endTimeTxt.SetValue(str(self.endTime))

    def onTimeTxt(self,event):
        """Event handler for Enter key in end time text """
        time = float(self.TimeTxt.GetValue())
        times = self.croco.wrapper.coords['time'].values
        # find index corresponding to the nearest instant time to plot
        self.timeIndex = min( range( len(times) ), \
            key=lambda j:abs(time-times[j]))
        self.time = self.croco.wrapper._get_date(self.timeIndex)
        self.TimeTxt.SetValue(str(self.time))
        self.updateVariableZ(setlim=False)

    # Event handler for zoom
    def onZoomBtn(self,event):    
        """Event handler for the button click Zoom in button"""   
        # self.figure.RS.set_active(True)
        self.toolbar.zoom()

    # Event handler for zoom
    def onPanBtn(self,event):    
        """Event handler for the button click Zoom in button"""   
        self.toolbar.pan()

    def onHomeBtn(self,event):
        """Event handler for the button click Zoom out button""" 
        self.xlim = [np.min(self.x),np.max(self.x)]
        self.ylim = [np.min(self.y),np.max(self.y)]
        # self.drawz(setlim=False)
        self.toolbar.home()

    # Event handler for Print
    def onSaveBtn(self,event):
        """Event handler for the button click Print button""" 
        # printDir = self.croco.startDir+"/Figures_" + self.croco.get_run_name()+"/"
        # if not os.path.isdir(printDir):
        #         os.mkdir(printDir)
        # # time = str(self.croco.wrapper._get_date(self.timeIndex))
        # filename = self.title.replace(',','_').replace(" ", "")+".png"
        # # filename = "{:s}_{:s}{:4.1f}_Time{:s}.png".format(self.variableName,self.slice,self.sliceCoord, \
        # #     time).replace(" ", "")
        # os.system('rm -rf '+printDir+filename)
        # self.figure.savefig(printDir+filename, dpi=self.figure.dpi)
        self.toolbar.save_figure(None)

    # Event handler for Color setup
    def onResetColorBtn(self,event):
        """Event handler for the button click Reset Color button""" 
        self.clim = [np.min(self.variable),np.max(self.variable)]
        self.MinColorTxt.SetValue('%.2E' % self.clim[0])
        self.MaxColorTxt.SetValue('%.2E' % self.clim[1])
        self.drawz(setlim=False)

    def onMinColorTxt(self,event):
        """Event handler for Enter key in Min Color text """
        self.clim[0] = float(self.MinColorTxt.GetValue())
        self.drawz(setlim=False)

    def onMaxColorTxt(self,event):
        """Event handler for Enter key in Max Color text """
        self.clim[1] = float(self.MaxColorTxt.GetValue())
        self.drawz(setlim=False)

    #------------- Methods of class

    def updateVariableZ(self,setlim=True):
        """ reload current variable depending on the time and plot it """
        try:
            self.variableZ = self.variable.isel(t=self.timeIndex)
        except:
            return
        self.drawz(setlim=setlim)


    def drawz(self, setlim=True):
        """ plot the current variable in the canvas """
        self.figure.clf()
        self.canvas.mpl_connect('button_press_event', self.onFigureClick)
        self.canvas.mpl_connect('motion_notify_event', self.ShowPosition)

        variableZ = ma.masked_invalid(self.variableZ.values)
        if setlim:
            self.mincolor = np.min(variableZ)
            self.MinColorTxt.SetValue('%.2E' % self.mincolor)
            self.maxcolor = np.max(variableZ)
            self.MaxColorTxt.SetValue('%.2E' % self.maxcolor)
            self.clim = [self.mincolor,self.maxcolor]
            self.xlim = [np.min(self.x), np.max(self.x)]
            self.ylim = [np.min(self.y), np.max(self.y)]
        time = str(self.croco.wrapper._get_date(self.timeIndex))
        self.title = "{:s}, {:s}={:4.1f}, Time={:s}".\
            format(self.variableName,self.slice,self.sliceCoord,time)
        mypcolor(self,self.x,self.y,variableZ,\
                      title=self.title,\
                      xlabel=self.xlabel,\
                      ylabel='Depth',\
                      xlim=self.xlim,\
                      ylim=self.ylim,\
                      clim=self.clim)

        self.canvas.draw()
        self.canvas.Refresh()
        self.Show()

# end of SectionFrame Class
########################################################################

class ProfileFrame(wx.Frame):
    """ 
    Window class to plot time series or depth profile.
    The window contains a canvas to plot, several buttons (zoom in, zoom out and 
    print ) 

    Attributes:
    croco : croco instance to study
    x : numpy array of x coordinates
    y : numpy array of y coordinates
    variableName : Name of the variable to plot in the canvas
    title : title of the plot
    xlabel : label of x axis
    ylabel : label of y axis
    """

    def __init__(self, croco=None, x=None, y=None, \
        variableName=None, title=None, xlabel=None, ylabel=None):

        # Create the window
        wx.Frame.__init__(self, None, wx.ID_ANY, title='Profile')

        # Now create the Panel to put the other controls on.
        self.panel = wx.Panel(self, wx.ID_ANY)

        # and a few controls
        self.figure = Figure()
        self.canvas = FigureCanvas(self.panel, -1, self.figure)       
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Hide()

        self.ZoomBtn = wx.Button(self.panel, wx.ID_ANY, "Zoom")
        self.HomeBtn = wx.Button(self.panel, wx.ID_ANY, "Home")
        self.PanBtn = wx.Button(self.panel, wx.ID_ANY, "Pan")
        self.SaveBtn = wx.Button(self.panel, wx.ID_ANY, "Save")


        # bind the menu event to an event handler
        self.ZoomBtn.Bind(wx.EVT_BUTTON, self.onZoomBtn)
        self.HomeBtn.Bind(wx.EVT_BUTTON, self.onHomeBtn)
        self.PanBtn.Bind(wx.EVT_BUTTON, self.onPanBtn)
        self.SaveBtn.Bind(wx.EVT_BUTTON, self.onSaveBtn)

        self.showPosition = self.CreateStatusBar(2)
        self.showPosition.SetStatusText("x=	  , y=  ",1)
        self.showPosition.SetStatusWidths([-1,150])

        self.__do_layout()

        # Initialize the variables of the class
        self.croco = croco
        self.x = x
        self.y = y
        self.variableName = variableName
        self.title = title
        self.xlabel=xlabel
        self.ylabel=ylabel

    def __do_layout(self):

        """
        Use a sizer to layout the controls, stacked vertically or horizontally
        """
        topSizer        = wx.BoxSizer(wx.VERTICAL)
        canvasSizer     = wx.BoxSizer(wx.VERTICAL)
        buttonsSizer    = wx.BoxSizer(wx.HORIZONTAL)


        canvasSizer.Add(self.canvas, 0, wx.ALL, 5)
        buttonsSizer.Add(self.ZoomBtn,0, wx.ALL, 5)
        buttonsSizer.Add(self.PanBtn,0, wx.ALL, 5)
        buttonsSizer.Add(self.HomeBtn,0, wx.ALL, 5)
        buttonsSizer.Add(self.SaveBtn,0, wx.ALL, 5)

        topSizer.Add(canvasSizer, 0, wx.CENTER)
        topSizer.Add(buttonsSizer, 0, wx.ALL|wx.EXPAND, 5)

        self.panel.SetSizer(topSizer)
        topSizer.Fit(self)

        self.Layout()

    # ------------ Event handler

    def rect_select_callback(self, eclick, erelease):
        """Event handler for rectangle selector on plot"""
        self.xPress, self.yPress = eclick.xdata, eclick.ydata
        self.xRelease, self.yRelease = erelease.xdata, erelease.ydata
        self.xlim = [min(self.xPress,self.xRelease),max(self.xPress,self.xRelease)]
        self.ylim = [ min(self.yPress,self.yRelease),max(self.yPress,self.yRelease)]
        self.draw(setlim=False)

    def ShowPosition(self, event):
        if event.inaxes:
            self.showPosition.SetStatusText(
                "x={:5.1f}  y={:5.1f}".format(event.xdata, event.ydata),1)

    def onZoomBtn(self,event): 
        """Event handler for the button click Zoom in button"""         
        # self.figure.RS.set_active(True)
        self.toolbar.zoom()

    def onHomeBtn(self,event):
        """Event handler for the button click Zoom out button"""   
        # self.draw()
        self.toolbar.home()

    def onPanBtn(self,event):
        """Event handler for the button click Zoom out button"""   
        # self.draw()
        self.toolbar.pan()

    def onSaveBtn(self,event):
        """Event handler for the button click Print button""" 
        # printDir = self.croco.startDir+"/Figures_" + self.croco.get_run_name()+"/"
        # if not os.path.isdir(printDir):
        #         os.mkdir(printDir)
        # filename = self.title.replace(",", "_").replace(" ","")+".png"
        # os.system('rm -Rf '+printDir+filename)
        # self.figure.savefig(printDir+filename, dpi=self.figure.dpi)
        self.toolbar.save_figure(None)

    #------------- Methods of class

    def draw(self, setlim=True):
        """ plot the current variable in the canvas """

        self.canvas.mpl_connect('motion_notify_event', self.ShowPosition)

        self.x = ma.masked_invalid(self.x)
        self.y = ma.masked_invalid(self.y)
        if setlim:
            self.xlim = [np.min(self.x), np.max(self.x)]
            self.ylim = [np.min(self.y), np.max(self.y)]
        title=self.title
        plotCurv(self,x=self.x,y=self.y,title=title,xlabel=self.xlabel, \
            ylabel=self.ylabel,xlim=self.xlim, ylim=self.ylim)
        self.canvas.draw()
        self.canvas.Refresh()
        self.Show()

# end of ProfileFrame Class
########################################################################

class CrocoGui(wx.Frame):
    """ 
    Window class to plot the XY sections, manage variables, times, levels and create 
    other windows for vertical sections and profiles

    Attributes:
    title : name of the window
    """

    def __init__(self):

        # Create the window
        wx.Frame.__init__(self, None, wx.ID_ANY, title='Main Window')
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Now create the Panel to put the other controls on.
        self.Panel = wx.Panel(self, wx.ID_ANY)

        # and a few controls
        # self.OpenFileBtn = wx.Button(self.Panel, wx.ID_ANY, "Open History File ...")
        # self.OpenFileTxt = wx.StaticText(self.Panel, wx.ID_ANY, " ", style=wx.ALIGN_LEFT)

        self.CrocoVariableChoice = wx.Choice(self.Panel, wx.ID_ANY, choices=["Croco Variables ..."])
        self.CrocoVariableChoice.SetSelection(0)

        self.DerivedVariableChoice = wx.Choice(self.Panel, wx.ID_ANY, choices=["Derived Variables ..."])
        self.DerivedVariableChoice.SetSelection(0)

        self.LabelTime = wx.StaticText(self.Panel,-1,label="Choose Time",style = wx.ALIGN_CENTER)
        self.LabelMinMaxTime = wx.StaticText(self.Panel, wx.ID_ANY, " ", style=wx.ALIGN_LEFT)
        self.TimeMinusBtn = wx.Button(self.Panel, wx.ID_ANY, "<")
        self.TimeTxt = wx.TextCtrl(self.Panel, wx.ID_ANY, "Time", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)
        self.TimePlusBtn = wx.Button(self.Panel, wx.ID_ANY, ">")

        self.LabelLevel = wx.StaticText(self.Panel,-1,label="Choose level (level>0, depth<0)",style = wx.ALIGN_CENTER)
        self.LabelMinMaxLevel = wx.StaticText(self.Panel, wx.ID_ANY, " ", style=wx.ALIGN_LEFT)
        self.LabelMinMaxDepth = wx.StaticText(self.Panel, wx.ID_ANY, " ", style=wx.ALIGN_LEFT)
        self.LevelMinusBtn = wx.Button(self.Panel, wx.ID_ANY, "<")
        self.LevelTxt = wx.TextCtrl(self.Panel, wx.ID_ANY, "Level", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)
        self.LevelPlusBtn = wx.Button(self.Panel, wx.ID_ANY, ">")

        self.LonSectionBtn = wx.Button(self.Panel, wx.ID_ANY, "Longitude Section")
        self.LonSectionTxt = wx.TextCtrl(self.Panel, wx.ID_ANY, "Longitude", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)
        self.LatSectionBtn = wx.Button(self.Panel, wx.ID_ANY, "Latitude Section")
        self.LatSectionTxt = wx.TextCtrl(self.Panel, wx.ID_ANY, "Latitude", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)
        # self.HovmullerBtn = wx.Button(self.Panel, wx.ID_ANY, "Hovmuller")
        self.TimeSeriesBtn = wx.Button(self.Panel, wx.ID_ANY, "Time Series")
        self.VerticalProfileBtn = wx.Button(self.Panel, wx.ID_ANY, "Vertical Profile")

        self.PanelCanvas = wx.Panel(self.Panel, -1)
        self.figure = Figure(figsize=(figsize[0],figsize[1]))
        self.canvas = FigureCanvas(self.PanelCanvas, -1, self.figure)        
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Hide()

        self.AnimationBtn = wx.Button(self.Panel, wx.ID_ANY, "Animation")
        self.startTimeTxt = wx.TextCtrl(self.Panel, wx.ID_ANY, "1", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)
        self.endTimeTxt = wx.TextCtrl(self.Panel, wx.ID_ANY, "1", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)
        self.ZoomBtn = wx.Button(self.Panel, wx.ID_ANY, "Zoom")        
        self.PanBtn = wx.Button(self.Panel, wx.ID_ANY, "Pan")
        self.HomeBtn = wx.Button(self.Panel, wx.ID_ANY, "Home")
        self.SaveBtn = wx.Button(self.Panel, wx.ID_ANY, "Save")

        self.ResetColorBtn = wx.Button(self.Panel, wx.ID_ANY, "Reset Color")
        self.MinColorTxt = wx.TextCtrl(self.Panel, wx.ID_ANY, "Min Color", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)
        self.MaxColorTxt = wx.TextCtrl(self.Panel, wx.ID_ANY, "Max Color", style=wx.TE_CENTRE|wx.TE_PROCESS_ENTER)

        # bind the menu event to an event handler
        # self.OpenFileBtn.Bind(wx.EVT_BUTTON, self.onOpenFile)
        self.CrocoVariableChoice.Bind(wx.EVT_CHOICE, self.onCrocoVariableChoice)
        self.DerivedVariableChoice.Bind(wx.EVT_CHOICE, self.onDerivedVariableChoice)
        self.ResetColorBtn.Bind(wx.EVT_BUTTON, self.onResetColorBtn)
        self.MinColorTxt.Bind(wx.EVT_TEXT_ENTER, self.onMinColorTxt)
        self.MaxColorTxt.Bind(wx.EVT_TEXT_ENTER, self.onMaxColorTxt)
        self.PanBtn.Bind(wx.EVT_BUTTON, self.onPanBtn)
        self.TimeMinusBtn.Bind(wx.EVT_BUTTON, self.onTimeMinusBtn)
        self.TimeTxt.Bind(wx.EVT_TEXT_ENTER, self.onTimeTxt)
        self.TimePlusBtn.Bind(wx.EVT_BUTTON, self.onTimePlusBtn)
        self.LevelMinusBtn.Bind(wx.EVT_BUTTON, self.onLevelMinusBtn)
        self.LevelPlusBtn.Bind(wx.EVT_BUTTON, self.onLevelPlusBtn)
        self.LevelTxt.Bind(wx.EVT_TEXT_ENTER, self.onLevelTxt)
        self.LonSectionBtn.Bind(wx.EVT_BUTTON, self.onLonSectionBtn)
        self.LonSectionTxt.Bind(wx.EVT_TEXT_ENTER, self.onLonSectionTxt)
        self.LatSectionBtn.Bind(wx.EVT_BUTTON, self.onLatSectionBtn)
        self.LatSectionTxt.Bind(wx.EVT_TEXT_ENTER, self.onLatSectionTxt)
        # self.HovmullerBtn.Bind(wx.EVT_BUTTON, self.onHovmullerBtn)
        self.TimeSeriesBtn.Bind(wx.EVT_BUTTON, self.onTimeSeriesBtn)
        self.VerticalProfileBtn.Bind(wx.EVT_BUTTON, self.onVerticalProfileBtn)
        self.AnimationBtn.Bind(wx.EVT_BUTTON, self.onAnimationBtn)
        self.startTimeTxt.Bind(wx.EVT_TEXT_ENTER, self.onstartTimeTxt)
        self.endTimeTxt.Bind(wx.EVT_TEXT_ENTER, self.onendTimeTxt)
        self.ZoomBtn.Bind(wx.EVT_BUTTON, self.onZoomBtn)
        self.PanBtn.Bind(wx.EVT_BUTTON, self.onPanBtn)
        self.HomeBtn.Bind(wx.EVT_BUTTON, self.onHomeBtn)
        self.SaveBtn.Bind(wx.EVT_BUTTON, self.onSaveBtn)

        self.showPosition = self.CreateStatusBar(2)
        self.showPosition.SetStatusText("x=	  , y=  ",1)
        self.showPosition.SetStatusWidths([-1,150])

        # self.__set_properties()
        self.__do_layout()

        # ceate a sectionFrame instance to plot XY section
        self.sectionXY = SectionFrame()

        self.openCroco()


    def __do_layout(self):

        """
        Use a sizer to layout the controls, stacked vertically or horizontally
        """

        topSizer        = wx.BoxSizer(wx.HORIZONTAL)
        leftSizer        = wx.BoxSizer(wx.VERTICAL)
        rightSizer        = wx.BoxSizer(wx.VERTICAL)
        # openFileSizer   = wx.BoxSizer(wx.VERTICAL)
        chooseVariablesSizer = wx.BoxSizer(wx.HORIZONTAL)
        labelTimeSizer  = wx.BoxSizer(wx.HORIZONTAL)
        labelMinMaxTimeSizer  = wx.BoxSizer(wx.HORIZONTAL)
        timeSizer       = wx.BoxSizer(wx.HORIZONTAL)
        labelLevelSizer  = wx.BoxSizer(wx.HORIZONTAL)
        labelMinMaxLevelSizer  = wx.BoxSizer(wx.HORIZONTAL)
        labelMinMaxDepthSizer  = wx.BoxSizer(wx.HORIZONTAL)
        levelSizer       = wx.BoxSizer(wx.HORIZONTAL)
        longitudeSizer  = wx.BoxSizer(wx.HORIZONTAL)
        latitudeSizer   = wx.BoxSizer(wx.HORIZONTAL)
        # hovmullerSizer  = wx.BoxSizer(wx.HORIZONTAL)
        timeSeriesSizer = wx.BoxSizer(wx.HORIZONTAL)
        profileSizer   = wx.BoxSizer(wx.HORIZONTAL)
        canvasSizer     = wx.BoxSizer(wx.VERTICAL)
        buttonsSizer    = wx.BoxSizer(wx.HORIZONTAL)
        animSizer       = wx.BoxSizer(wx.HORIZONTAL)
        colorSizer      = wx.BoxSizer(wx.HORIZONTAL)

        # openFileSizer.Add(self.OpenFileBtn, 0, wx.ALL, 5)
        # openFileSizer.Add(self.OpenFileTxt, 1, wx.ALL|wx.EXPAND, 5)
        chooseVariablesSizer.Add(self.CrocoVariableChoice, 0, wx.ALL, 5)
        chooseVariablesSizer.Add(self.DerivedVariableChoice, 0, wx.ALL, 5)

        labelTimeSizer.Add(self.LabelTime, 0, wx.ALL|wx.EXPAND, 5)
        labelMinMaxTimeSizer.Add(self.LabelMinMaxTime, 0, wx.ALL|wx.EXPAND, 5)
        timeSizer.Add(self.TimeMinusBtn, 0, wx.ALL, 5)
        timeSizer.Add(self.TimeTxt, 0, wx.ALL, 5)
        timeSizer.Add(self.TimePlusBtn, 0, wx.ALL, 5)

        labelLevelSizer.Add(self.LabelLevel, 0, wx.ALL|wx.EXPAND, 5)
        labelMinMaxLevelSizer.Add(self.LabelMinMaxLevel, 0, wx.ALL|wx.EXPAND, 5)
        labelMinMaxDepthSizer.Add(self.LabelMinMaxDepth, 0, wx.ALL|wx.EXPAND, 5)
        levelSizer.Add(self.LevelMinusBtn, 0, wx.ALL, 5)
        levelSizer.Add(self.LevelTxt, 0, wx.ALL, 5)
        levelSizer.Add(self.LevelPlusBtn, 0, wx.ALL, 5)

        longitudeSizer.Add(self.LonSectionBtn, 0, wx.ALL, 5)
        longitudeSizer.Add(self.LonSectionTxt, 0, wx.ALL, 5)

        latitudeSizer.Add(self.LatSectionBtn, 0, wx.ALL, 5)
        latitudeSizer.Add(self.LatSectionTxt, 0, wx.ALL, 5)

        # hovmullerSizer.Add(self.HovmullerBtn, 0, wx.ALL, 5)

        timeSeriesSizer.Add(self.TimeSeriesBtn, 0, wx.ALL, 5)

        profileSizer.Add(self.VerticalProfileBtn, 0, wx.ALL, 5)

        canvasSizer.Add(self.PanelCanvas, 1, wx.EXPAND , 5)

        buttonsSizer.Add(self.ZoomBtn,0, wx.ALL, 5)
        buttonsSizer.Add(self.PanBtn,0, wx.ALL, 5)
        buttonsSizer.Add(self.HomeBtn,0, wx.ALL, 5)
        buttonsSizer.Add(self.SaveBtn,0, wx.ALL, 5)

        animSizer.Add(self.AnimationBtn,0, wx.ALL, 5)
        animSizer.Add(self.startTimeTxt,0, wx.ALL, 5)
        animSizer.Add(self.endTimeTxt,0, wx.ALL, 5)

        colorSizer.Add(self.ResetColorBtn, 0, wx.ALL, 5)
        colorSizer.Add(self.MinColorTxt, 0, wx.ALL, 5)
        colorSizer.Add(self.MaxColorTxt, 0, wx.ALL, 5)

        # leftSizer.Add(openFileSizer, 0,wx.ALL|wx.EXPAND, 5 )
        leftSizer.Add(chooseVariablesSizer, 0, wx.ALL|wx.EXPAND, 5)
        leftSizer.Add(labelTimeSizer, 0, wx.ALL|wx.EXPAND, 5)
        leftSizer.Add(labelMinMaxTimeSizer, 0, wx.ALL|wx.EXPAND, 5)
        leftSizer.Add(timeSizer, 0, wx.ALL|wx.EXPAND, 5)
        leftSizer.Add(labelLevelSizer, 0, wx.ALL|wx.EXPAND, 5)
        leftSizer.Add(labelMinMaxLevelSizer, 0, wx.ALL|wx.EXPAND, 5)
        leftSizer.Add(labelMinMaxDepthSizer, 0, wx.ALL|wx.EXPAND, 5)
        leftSizer.Add(levelSizer, 0, wx.ALL|wx.EXPAND, 5)
        leftSizer.Add(longitudeSizer, 0, wx.ALL|wx.EXPAND, 5)
        leftSizer.Add(latitudeSizer, 0, wx.ALL|wx.EXPAND, 5)
        # leftSizer.Add(hovmullerSizer, 0, wx.ALL|wx.EXPAND, 5)
        leftSizer.Add(timeSeriesSizer, 0, wx.ALL|wx.EXPAND, 5)
        leftSizer.Add(profileSizer, 0, wx.ALL|wx.EXPAND, 5)
        rightSizer.Add(canvasSizer, 0, wx.EXPAND)
        rightSizer.Add(buttonsSizer, 0, wx.ALL|wx.EXPAND, 5)
        rightSizer.Add(animSizer, 0, wx.ALL|wx.EXPAND, 5)
        rightSizer.Add(colorSizer, 0, wx.ALL|wx.EXPAND, 5)

        topSizer.Add(leftSizer, 0,wx.ALL|wx.EXPAND, 5 )
        topSizer.Add(rightSizer, 0,wx.EXPAND, 5 )

        self.Panel.SetSizer(topSizer)
        self.Panel.SetAutoLayout(True)
        topSizer.Fit(self)

        self.Layout()

    # ------------ Event handler

    def OnClose(self,event):
        self.Destroy()
        sys.exit()


    def onFigureClick(self,event):
        self.lon, self.lat = event.xdata, event.ydata
        self.latIndex,self.lonIndex = self.findLatLonIndex(self.lon, self.lat)
        self.LonSectionTxt.SetValue('%.2F' % self.lon)
        self.LatSectionTxt.SetValue('%.2F' % self.lat)

    def ShowPosition(self, event):
        if event.inaxes:
            self.showPosition.SetStatusText(
                "x={:5.1f}  y={:5.1f}".format(event.xdata, event.ydata),1)

    def rect_select_callback(self, eclick, erelease):
        self.xPress, self.yPress = eclick.xdata, eclick.ydata
        self.xRelease, self.yRelease = erelease.xdata, erelease.ydata
        self.xlim = [min(self.xPress,self.xRelease),max(self.xPress,self.xRelease)]
        self.ylim = [ min(self.yPress,self.yRelease),max(self.yPress,self.yRelease)]
        self.drawxy(setlim=False)

    # def onOpenFile(self, event):
    def openCroco(self):
        """
        Create and show the Open FileDialog to select file name
        Initialize few outputs
        """

        startDir = os.getcwd()
        # dlg = wx.FileDialog(
        #     self, message="Choose a file",
        #     defaultDir=startDir, 
        #     defaultFile="",
        #     wildcard=wildcard,
        #     style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_CHANGE_DIR
        #     )
        # if dlg.ShowModal() == wx.ID_OK:
        #     paths = dlg.GetPaths()
        # dlg.Destroy()
        self.croco = Croco() 
        self.croco.startDir = startDir

        # Fill the different text of the main window
        timeMin = self.croco.wrapper._get_date(0)
        timeMax = self.croco.wrapper._get_date(self.croco.wrapper.ntimes-1)
        self.LabelMinMaxTime.SetLabel("Min/Max Time = "+str(timeMin)+" ... "+str(timeMax)+ "days") 
        self.TimeTxt.SetValue(str(timeMin))
        self.timeIndex = 0
        self.time = timeMin
        minLevel = 1
        maxLevel = int(self.croco.wrapper.N)
        minDepth = - int(self.croco.wrapper.metrics['h'].max())
        maxDepth = 0
        self.LabelMinMaxLevel.SetLabel("Min/Max Level = 1 ... "+ str(maxLevel))
        self.LabelMinMaxDepth.SetLabel("Min/Max Depth = "+ str(minDepth)+" ... "+str(maxDepth))
        self.levelIndex=self.croco.wrapper.N - 1
        self.LevelTxt.SetValue(str(self.levelIndex+1))
        self.depth = self.levelIndex + 1
        self.startTimeTxt.SetValue(str(timeMin))
        self.startTime = timeMin
        self.startTimeIndex = 0
        self.endTimeTxt.SetValue(str(timeMax))
        self.endTime = timeMax
        self.endTimeIndex = self.croco.wrapper.ntimes -1
        self.CrocoVariableChoice.AppendItems(self.croco.ListOfVariables)
        self.DerivedVariableChoice.AppendItems(self.croco.ListOfDerived)

        lon = self.croco.get_coord('ssh', direction='x')
        self.lon = lon[int(0.5*self.croco.wrapper.M),int(0.5*self.croco.wrapper.L)]
        lat = self.croco.get_coord('ssh', direction='y')
        self.lat = lat[int(0.5*self.croco.wrapper.M),int(0.5*self.croco.wrapper.L)]
        self.latIndex,self.lonIndex = self.findLatLonIndex(self.lon, self.lat)
        self.LonSectionTxt.SetValue('%.2F' % self.lon)
        self.LatSectionTxt.SetValue('%.2F' % self.lat)


    def onCrocoVariableChoice(self, event):
        ''' Choose variable from croco file to plot '''
        self.variableName = self.CrocoVariableChoice.GetString(self.CrocoVariableChoice.GetSelection())
        self.DerivedVariableChoice.SetSelection(0)
        self.updateVariableXY()

    def onDerivedVariableChoice(self, event):
        ''' Choose a computed variable to plot '''
        self.variableName = self.DerivedVariableChoice.GetString(self.DerivedVariableChoice.GetSelection())
        self.CrocoVariableChoice.SetSelection(0)
        self.updateVariableXY()

    def onResetColorBtn(self,event):
        variableXY = ma.masked_invalid(self.variableXY.values)
        self.clim = [np.min(variableXY),np.max(variableXY)]
        self.MinColorTxt.SetValue('%.2E' % self.clim[0])
        self.MaxColorTxt.SetValue('%.2E' % self.clim[1])
        self.drawxy(setlim=False)

    def onPanBtn(self,event):
        self.toolbar.pan()

    def onMinColorTxt(self,event):
        self.clim[0] = float(self.MinColorTxt.GetValue())
        self.drawxy(setlim=False)

    def onMaxColorTxt(self,event):
        self.clim[1] = float(self.MaxColorTxt.GetValue())
        self.drawxy(setlim=False)


    def onTimeMinusBtn(self,event):
        self.timeIndex = max(self.timeIndex - 1,0)
        self.time = self.croco.wrapper._get_date(self.timeIndex)
        self.TimeTxt.SetValue(str(self.time))
        self.updateVariableXY(setlim=False)

    def onTimePlusBtn(self,event):
        self.timeIndex = min(self.timeIndex + 1,self.croco.wrapper.ntimes - 1)
        self.time = self.croco.wrapper._get_date(self.timeIndex)
        self.TimeTxt.SetValue(str(self.time))
        self.updateVariableXY(setlim=False)

    def onTimeTxt(self,event):
        time = float(self.TimeTxt.GetValue())
        times = self.croco.wrapper.coords['time'].values
        # find index corresponding to the nearest instant time to plot
        self.timeIndex = min( range( len(times) ), \
            key=lambda j:abs(time-times[j]))
        self.time = self.croco.wrapper._get_date(self.timeIndex)
        self.TimeTxt.SetValue(str(self.time))
        self.updateVariableXY(setlim=False)

    def onLevelMinusBtn(self,event):
        self.levelIndex = max(self.levelIndex - 1,0)
        self.depth = self.levelIndex + 1
        self.LevelTxt.SetValue(str(self.levelIndex + 1))
        self.updateVariableXY(setlim=False)

    def onLevelPlusBtn(self,event):
        self.levelIndex = min(self.levelIndex + 1,self.croco.wrapper.N - 1)
        self.depth = self.levelIndex + 1
        self.LevelTxt.SetValue(str(self.levelIndex + 1))
        self.updateVariableXY(setlim=False)

    def onLevelTxt(self,event):
        depth = float(self.LevelTxt.GetValue())
        if depth > 0:
            self.levelIndex = min(int(depth-1),self.croco.wrapper.N - 1)
            self.LevelTxt.SetValue(str(self.levelIndex + 1))
        else:
            ssh = self.croco.variables['ssh'].isel(t=self.timeIndex).values
            z = self.croco.wrapper.scoord2z_r(ssh, alpha=0., beta=0)
            self.levelIndex = np.argmax(z[:,self.latIndex,self.lonIndex]>=depth)
        self.updateVariableXY(setlim=False)

    def onLonSectionBtn(self,event):
        # if variable without z dimension
        try:
            ndims=len(self.croco.variables[self.variableName].dims)
        except:
            ndims=4
        if ndims < 4 :
            print("Not 3D variable")
            return
        self.drawz(typSection="YZ")

    def onLonSectionTxt(self,event):
        # if variable without z dimension
        try:
            ndims=len(self.croco.variables[self.variableName].dims)
        except:
            ndims=4
        if ndims < 4 :
            print("Not 3D variable")
            return
        self.lon = float(self.LonSectionTxt.GetValue())
        # Find nearest indices of selected point
        self.latIndex,self.lonIndex = self.findLatLonIndex(self.lon, self.lat) 
        self.drawz(typSection="YZ")

    def onLatSectionBtn(self,event):
        # if variable without z dimension
        try:
            ndims=len(self.croco.variables[self.variableName].dims)
        except:
            ndims=4
        if ndims < 4 :
            print("Not 3D variable")
            return
        self.drawz(typSection="XZ")

    def onLatSectionTxt(self,event):
        # if variable without z dimension
        try:
            ndims=len(self.croco.variables[self.variableName].dims)
        except:
            ndims=4
        if ndims < 4 :
            print("Not 3D variable")
            return   
        self.lat = float(self.LatSectionTxt.GetValue())
        # Find nearest indices of selected point
        self.latIndex,self.lonIndex = self.findLatLonIndex(self.lon, self.lat) 
        self.drawz(typSection="XZ")

    def onTimeSeriesBtn(self,event):
        depth = float(self.LevelTxt.GetValue())

        # Get the mask at the rigth point
        try:
            dims = self.croco.variables[self.variableName].dims
        except:
            dims = []
        mask = self.croco.wrapper.masks['mask_r']
        if "x_u" in dims:
            mask = self.croco.rho2u_2d(mask)
        elif "y_v" in dims:
            mask = self.croco.rho2v_2d(mask)
        # mask = np.where(mask==0.,np.nan,mask)

        # Get x coordinate: time
        x = self.croco.wrapper.coords['time'].values.astype('timedelta64[D]').astype('float')
        
        # Time series on level    
        if depth > 0:
            # Variable from croco file
            if self.variableName in self.croco.ListOfVariables:
                y = self.croco.get_variable(self.variableName, \
                    xindex=self.lonIndex, yindex=self.latIndex, zindex=self.levelIndex).values

            # Derived variable
            elif self.variableName in self.croco.ListOfDerived:
                y = np.zeros_like(x)
                for it in range(len(x)):
                    if 'pv' in self.variableName:
                        y[it] = get_pv(self.croco,it, depth=self.levelIndex,typ=self.variableName)\
                                [self.latIndex,self.lonIndex]
                    elif self.variableName == 'zeta_k':
                        y[it] = get_zetak(self.croco,it, depth=self.levelIndex)\
                        	    [self.latIndex,self.lonIndex]
                    elif self.variableName == 'dtdz':
                        y[it] = get_dtdz(self.croco,it, depth=self.levelIndex)\
                        	    [self.latIndex,self.lonIndex]

            title="{:s}, Lon={:4.1f}, Lat={:4.1f}, Level={:4.0f}".\
                format(self.variableName,self.lon,self.lat, self.depth) 

        # Time series on depth
        else:

            y = np.zeros_like(x)
            # recalculate the depth slice at each time step
            for it in range(len(x)):
                # Calculate z        
                ssh = self.croco.variables['ssh'].isel(t=self.timeIndex).values
                if self.variableName=="u":
                    z = self.croco.wrapper.scoord2z_u(ssh, alpha=0., beta=0)
                elif self.variableName=="v":
                    z = self.croco.wrapper.scoord2z_v(ssh, alpha=0., beta=0)
                else :
                    z = self.croco.wrapper.scoord2z_r(ssh, alpha=0., beta=0)

                if self.variableName in self.croco.ListOfVariables:    
                    # Find levels around depth
                    maxlev = np.argmax(z[:,self.latIndex,self.lonIndex]>=depth)
                    minlev = maxlev-1  
                    z1 = z[minlev,self.latIndex,self.lonIndex]
                    z2 = z[maxlev,self.latIndex,self.lonIndex]
                    # read variable and do interpolation
                    var = self.croco.variables[self.variableName].isel(t=it, \
                             z_r=slice(minlev,maxlev+1))[:,self.latIndex,self.lonIndex]
                    y[it]=((var[0]-var[1])*depth+var[1]*z1-var[0]*z2)/(z1-z2) 
            
                elif self.variableName in self.croco.ListOfDerived:
                    # Find all the level corresponding to depth
                    minlev,maxlev = self.croco.zslice(None,mask,z,depth,findlev=True)
                    if 'pv' in self.variableName:
                        # Compute pv between these levels
                        var = get_pv(self.croco,it, depth=depth, minlev=minlev, maxlev=maxlev,\
                        	   typ=self.variableName)
                        # Extract the slice of pv corresponding at the depth
                        try:
                            varz = self.croco.zslice(var,mask,z[minlev:maxlev,:,:],depth)[0]
                        except:
                            print("Not enough points")
                            pass
                        y[it]=varz[self.latIndex,self.lonIndex]

                    elif self.variableName == 'zeta_k':
                        # Compute pv between these levels
                        var = get_zetak(self.croco,it, depth=depth, minlev=minlev, maxlev=maxlev)
                        # Extract the slice of pv corresponding at the depth
                        try:
                            varz = self.croco.zslice(var,mask,z[minlev:maxlev,:,:],depth)[0]
                        except:
                            print("Not enough points")
                            pass
                        y[it]=varz[self.latIndex,self.lonIndex]

                    elif self.variableName == 'dtdz':
                        # Compute pv between these levels
                        var = get_dtdz(self.croco,it, depth=depth, minlev=minlev, maxlev=maxlev)
                        # Extract the slice of pv corresponding at the depth
                        try:
                            varz = self.croco.zslice(var,mask,z[minlev:maxlev,:,:],depth)[0]
                        except:
                            print("Not enough points")
                            pass
                        y[it]=varz[self.latIndex,self.lonIndex]

            title="{:s}, Lon={:4.1f}, Lat={:4.1f}, depth={:4.1f}".\
                format(self.variableName,self.lon,self.lat,depth)

        # Plot the time series
        self.timeFrame = ProfileFrame(croco=self.croco, \
            x=x, y=y, \
            variableName=self.variableName, \
            title=title, \
            xlabel="Time (days)")
        self.timeFrame.draw()

    def onVerticalProfileBtn(self,event):
        # Dimension must have z coordinate
        try:
            ndims = self.croco.variables[self.variableName].dims
        except:
            ndims = 4               
        if ndims < 4 :
            print("Not 3D variable")
            return

        time = str(self.croco.wrapper._get_date(self.timeIndex))
        title="{:s}, Lon={:4.1f}, Lat={:4.1f}, Time={:s}".\
            format(self.variableName,self.lon,self.lat,time)
        # Get depths coordinate
        ssh = self.croco.variables['ssh'].isel(t=self.timeIndex).values
        if self.variableName=="u":
            z = self.croco.wrapper.scoord2z_u(ssh, alpha=0., beta=0)[:,self.latIndex,self.lonIndex]
        elif self.variableName=="v":
            z = self.croco.wrapper.scoord2z_v(ssh, alpha=0., beta=0)[:,self.latIndex,self.lonIndex]
        else :
            z = self.croco.wrapper.scoord2z_r(ssh, alpha=0., beta=0)[:,self.latIndex,self.lonIndex]

        # Get variable profile
        if self.variableName in self.croco.ListOfVariables: 
            x = self.croco.get_variable(self.variableName, \
                xindex=self.lonIndex, yindex=self.latIndex, tindex=self.timeIndex).values
        
        elif self.variableName in self.croco.ListOfDerived:
            if 'pv' in self.variableName:
                x = np.full_like(z, np.nan)
                var = get_pv(self.croco,self.timeIndex, \
                	minlev=0, maxlev=self.croco.wrapper.N-1,\
                	lonindex=self.lonIndex, typ=self.variableName)
                x[1:] = var[:,self.latIndex]

            elif self.variableName == 'zeta_k':
                x = np.full_like(z, np.nan)
                var = get_zetak(self.croco,self.timeIndex, \
                	minlev=0, maxlev=self.croco.wrapper.N-1,\
                	lonindex=self.lonIndex,)
                x[1:] = var[:,self.latIndex]

            elif self.variableName == 'dtdz':
                x = np.full_like(z, np.nan)
                var = get_dtdz(self.croco,self.timeIndex, \
                	minlev=0, maxlev=self.croco.wrapper.N-1,\
                	lonindex=self.lonIndex,)
                x[1:] = var[:,self.latIndex]

        # Plot the profile
        self.profileFrame = ProfileFrame(croco=self.croco, \
            x=x, y=z, \
            variableName=self.variableName, \
            title=title,
            ylabel="Depth (m)")
        self.profileFrame.draw()

    def onAnimationBtn(self,event):
        printDir = self.croco.startDir+"/Figures_" + self.croco.get_run_name()+"/"
        if not os.path.isdir(printDir):
                os.mkdir(printDir)
        time1 = str(self.croco.wrapper._get_date(self.startTimeIndex))
        time2 = str(self.croco.wrapper._get_date(self.endTimeIndex))
        depth = float(self.LevelTxt.GetValue())
        if depth>0:
            filename = "{:s}_Level={:4.0f}_Time={:s}-{:s}.mp4".format(self.variableName,self.depth,time1,time2)
        else:
            filename = "{:s}_Depth={:4.0f}_Time={:s}-{:s}.mp4".format(self.variableName,self.depth,time1,time2)
        filename=filename.replace(" ","")

        # self.clim = [np.min(self.variableXY),np.max(self.variableXY)]
        save_count = self.endTimeIndex - self.startTimeIndex + 1
        anim = animation.FuncAnimation(self.figure, self.animate, \
                   frames = range(self.startTimeIndex,self.endTimeIndex+1), repeat=False, \
                   blit = False, save_count=save_count)
        anim.save(printDir+filename, writer="ffmpeg")
        # self.canvas.draw()

    def animate( self, i):
        # Method done at each time step of the animation
        self.timeIndex = i
        self.updateVariableXY(setlim=False)

    def onstartTimeTxt(self,event):
        self.startTime = float(self.startTimeTxt.GetValue())
        times = self.croco.wrapper.coords['time'].values
        # find index corresponding to instant time to plot
        self.startTimeIndex = min( range( len(times) ), \
            key=lambda j:abs(self.startTime-times[j]))
        self.startTime = self.croco.wrapper._get_date(self.startTimeIndex)
        self.startTimeTxt.SetValue(str(self.startTime))

    def onendTimeTxt(self,event):
        self.endTime = float(self.endTimeTxt.GetValue())
        times = self.croco.wrapper.coords['time'].values
        # find index corresponding to instant time to plot
        self.endTimeIndex = min( range( len(times) ), \
            key=lambda j:abs(self.endTime-times[j]))
        self.endTime = self.croco.wrapper._get_date(self.endTimeIndex)
        self.endTimeTxt.SetValue(str(self.endTime))

    def onZoomBtn(self,event):
        # Activate the selection rectangle to zoom
        # self.figure.RS.set_active(True)       
        self.toolbar.zoom()

    def onPanBtn(self,event):
        # Activate the selection rectangle to zoom
        # self.figure.RS.set_active(True)       
        self.toolbar.pan()

    def onHomeBtn(self,event):
        # self.xlim = [np.min(self.croco.wrapper.coords['lon_r'].values), \
        #              np.max(self.croco.wrapper.coords['lon_r'].values)]
        # self.ylim = [np.min(self.croco.wrapper.coords['lat_r'].values), \
        #              np.max(self.croco.wrapper.coords['lat_r'].values)]
        self.xlim = [np.min(self.croco.wrapper.coords['lon_r']), \
                     np.max(self.croco.wrapper.coords['lon_r'])]
        self.ylim = [np.min(self.croco.wrapper.coords['lat_r']), \
                     np.max(self.croco.wrapper.coords['lat_r'])]
        # self.drawxy(setlim=False)        
        self.toolbar.home()

    def onSaveBtn(self,event):
        # printDir = self.croco.startDir+"/Figures_" + self.croco.get_run_name()+"/"
        # if not os.path.isdir(printDir):
        #         os.mkdir(printDir)
        # # time = str(self.croco.wrapper._get_date(self.timeIndex))
        # # filename = "{:s}_Depth={:4.0f}_Time{:s}".format(self.variableName,self.depth,time)
        # # filename=filename.replace(" ","")+".png"
        # filename = self.title.replace(',','_').replace(" ", "")+".png"
        # os.system('rm -rf '+printDir+filename)
        # self.figure.savefig(printDir+filename, dpi=self.figure.dpi)
        self.toolbar.save_figure(None)


    #------------- Methods of class


    def findLatLonIndex(self, lonValue, latValue):
        ''' Find nearest  grid point of  click value '''
        # a = abs(self.croco.wrapper.coords['lon_r'].values - lonValue) + \
        #     abs(self.croco.wrapper.coords['lat_r'].values - latValue)
        a = abs(self.croco.wrapper.coords['lon_r'] - lonValue) + \
            abs(self.croco.wrapper.coords['lat_r'] - latValue)
        return np.unravel_index(a.argmin(),a.shape)


    def updateVariableXY(self,setlim=True):
        ''' Fill the variable self.variableXY with the rigth data'''
        time = str(self.timeIndex)        
        depth = float(self.LevelTxt.GetValue())

        try:
            dims = self.croco.variables[self.variableName].dims
        except:
            dims = []

        # if 2D variable, reset level
        if len(dims)==3 :
        	depth = 120
        	self.LevelTxt.SetValue(str(depth))

        mask = self.croco.wrapper.masks['mask_r']
        if "x_u" in dims:
            mask = self.croco.rho2u_2d(mask)
        elif "y_v" in dims:
            mask = self.croco.rho2v_2d(mask)
        mask = np.where(mask==0.,np.nan,mask)

        # Level plot
        if depth > 0:
            self.levelIndex = int(self.LevelTxt.GetValue()) - 1
            self.depth = self.levelIndex + 1
            if self.variableName in self.croco.ListOfVariables:
                try:
                    self.variableXY = self.croco.variables[self.variableName].isel(t=self.timeIndex,z_r=self.levelIndex)
                except:
                    self.variableXY = self.croco.variables[self.variableName].isel(t=self.timeIndex)

            elif self.variableName in self.croco.ListOfDerived:
                if 'pv' in self.variableName:
                    var = get_pv(self.croco,self.timeIndex, depth=depth, typ=self.variableName)
                    self.variableXY = xr.DataArray(data=var)
                elif self.variableName == 'zeta_k':
                    var = get_zetak(self.croco,self.timeIndex, depth=depth)
                    self.variableXY = xr.DataArray(data=var)
                elif self.variableName == 'dtdz':
                    var = get_dtdz(self.croco,self.timeIndex, depth=depth)
                    self.variableXY = xr.DataArray(data=var)
            else:
                print("unknown variable ",self.variableName)
                return

        # Depth plot
        elif depth <= 0:
            self.depth = depth
            # Calculate depths 
            ssh = self.croco.variables['ssh'].isel(t=self.timeIndex).values
            if self.variableName=="u":
                z = self.croco.wrapper.scoord2z_u(ssh, alpha=0., beta=0)
            elif self.variableName=="v":
                z = self.croco.wrapper.scoord2z_v(ssh, alpha=0., beta=0)
            else :
                z = self.croco.wrapper.scoord2z_r(ssh, alpha=0., beta=0)
            minlev,maxlev = self.croco.zslice(None,mask,z,depth,findlev=True)


            # Variable from croco file
            if self.variableName in self.croco.ListOfVariables:      
                var = self.croco.variables[self.variableName].isel(t=self.timeIndex, z_r=slice(minlev,maxlev+1))
                try:
                    zslice = self.croco.zslice(var.values,mask,z[minlev:maxlev+1,:,:],depth)[0]
                    self.variableXY = xr.DataArray(data=zslice)
                except:
                    print("Not enough points")

            # Derived variable
            elif self.variableName in self.croco.ListOfDerived:
                if 'pv' in self.variableName:
                    var = get_pv(self.croco,self.timeIndex, depth=depth, minlev=minlev, maxlev=maxlev,typ=self.variableName)
                    try:
                        zslice = self.croco.zslice(var,mask,z[minlev:maxlev,:,:],depth)[0]
                        self.variableXY = xr.DataArray(data=zslice)
                    except:
                        print("Not enough points")
                        pass
        
                elif self.variableName== 'zeta_k':
                    var = get_zetak(self.croco,self.timeIndex, depth=depth, minlev=minlev, maxlev=maxlev)
                    try:
                        zslice = self.croco.zslice(var,mask,z[minlev:maxlev,:,:],depth)[0]
                        self.variableXY = xr.DataArray(data=zslice)
                    except:
                        print("Not enough points")
                        pass
        
                elif self.variableName== 'dtdz':
                    var = get_dtdz(self.croco,self.timeIndex, depth=depth, minlev=minlev, maxlev=maxlev)
                    try:
                        zslice = self.croco.zslice(var,mask,z[minlev:maxlev,:,:],depth)[0]
                        self.variableXY = xr.DataArray(data=zslice)
                    except:
                        print("Not enough points")
                        pass
        # Draw the new self.variableXY  
        self.variableXY.values = mask*self.variableXY.values             
        self.drawxy(setlim=setlim)


    def drawxy(self,setlim=True):
        ''' Draw the current variable self.variableXY in the canvas of the main window '''
        self.figure.clf()
        # Prepare the canvas to receive click events
        self.canvas.mpl_connect('button_press_event', self.onFigureClick)
        self.canvas.mpl_connect('motion_notify_event', self.ShowPosition)
        variableXY = ma.masked_invalid(self.variableXY.values)
        # Set default parameters of the plot if needed
        if setlim:
            self.mincolor = np.min(variableXY)
            self.MinColorTxt.SetValue('%.2E' % self.mincolor)
            self.maxcolor = np.max(variableXY)
            self.MaxColorTxt.SetValue('%.2E' % self.maxcolor)
            self.clim = [self.mincolor,self.maxcolor]
            self.xlim = [np.min(self.croco.wrapper.coords['lon_r']), \
                         np.max(self.croco.wrapper.coords['lon_r'])]
            self.ylim = [np.min(self.croco.wrapper.coords['lat_r']), \
                         np.max(self.croco.wrapper.coords['lat_r'])]


        time = str(self.croco.wrapper._get_date(self.timeIndex))
        depth = float(self.LevelTxt.GetValue())
        lon = self.croco.wrapper.coords['lon_r']
        lat = self.croco.wrapper.coords['lat_r']

        if depth > 0:
            self.title = "{:s}, Level={:4d}, Time={:s}".format(self.variableName,self.levelIndex+1,time)
        else:
            self.title = "{:s}, Depth={:4.1f}, Time={:s}".format(self.variableName,depth,time)
        mypcolor(self,lon,lat,variableXY,\
                      title=self.title,\
                      xlabel='Longitude',\
                      ylabel='Latitude',\
                      xlim=self.xlim,\
                      ylim=self.ylim,\
                      clim=self.clim)
        
        self.canvas.draw()
        self.canvas.Refresh()
        self.Refresh()

    def drawz(self,typSection=None):
        ''' Extract the  rigth section for the current variable and plot in a new window '''

        # Latitude section
        if typSection == "XZ":        
            ssh = self.croco.variables['ssh'].isel(t=self.timeIndex,\
            	            y_r=slice(self.latIndex-1,self.latIndex+2)).values

            # Variable from croco file
            if self.variableName in self.croco.ListOfVariables:
                variable = self.croco.get_variable(self.variableName, \
                    yindex=self.latIndex)
            # Derived Variable
            elif self.variableName in self.croco.ListOfDerived:       
                ntimes = self.croco.wrapper.ntimes
                N = self.croco.wrapper.N
                L = self.croco.wrapper.L
                variable = self.croco.create_DataArray(data=np.zeros((ntimes,N,L)), dimstyp='xzt')
                for it in range(ntimes):
                    if 'pv' in self.variableName:
                        variable[it,1:,:] = get_pv(self.croco,self.timeIndex, \
                        	minlev=0, maxlev=self.croco.wrapper.N-1,\
                        	latindex=self.latIndex, typ=self.variableName)
                
                    elif self.variableName == 'zeta_k':
                        variable[it,1:,:] = get_zetak(self.croco,self.timeIndex, \
                        	minlev=0, maxlev=self.croco.wrapper.N-1, \
                        	latindex=self.latIndex)
                
                    elif self.variableName == 'dtdz':
                        variable[it,1:,:] = get_dtdz(self.croco,self.timeIndex, \
                        	minlev=0, maxlev=self.croco.wrapper.N-1, \
                        	latindex=self.latIndex)
                
            # Get Longitude coordinates
            x = self.croco.get_coord(self.variableName, direction='x')
            x = repmat(x[self.latIndex,:].squeeze(),self.croco.wrapper.N,1)
            # Get depths coordinates
            if self.variableName=="u":
                y = np.squeeze(self.croco.wrapper.scoord2z_u(ssh, alpha=0., beta=0, latindex=self.latIndex)[:,1:-1,:])
            elif self.variableName=="v":
                y = np.squeeze(self.croco.wrapper.scoord2z_v(ssh, alpha=0., beta=0, latindex=self.latIndex)[:,1:,:])
            else :
                y = np.squeeze(self.croco.wrapper.scoord2z_r(ssh, alpha=0., beta=0, latindex=self.latIndex)[:,1:-1,:])
            # Create new window
            self.sectionXZ = SectionFrame(\
                croco=self.croco, \
                variableName = self.variableName, \
                variable=variable, 
                x=x, y=y, \
                typSection="XZ" , \
                sliceCoord = self.lat, \
                timeIndex=self.timeIndex)
            # Draw the plot
            self.sectionXZ.updateVariableZ()

        # Longitude section
        elif typSection == "YZ":       
            ssh = self.croco.variables['ssh'].isel(t=self.timeIndex,\
            	          x_r=slice(self.lonIndex-1,self.lonIndex+2)).values

            # Variable from croco file
            if self.variableName in self.croco.ListOfVariables:
                variable = self.croco.get_variable(self.variableName, \
                    xindex=self.lonIndex)
            # Derived Variable
            elif self.variableName in self.croco.ListOfDerived: 
                ntimes = self.croco.wrapper.ntimes
                N = self.croco.wrapper.N
                M = self.croco.wrapper.M
                variable = self.croco.create_DataArray(data=np.zeros((ntimes,N,M)), dimstyp='yzt')
                for it in range(ntimes):
                    if 'pv' in self.variableName:
                        variable[it,1:,:] = get_pv(self.croco,self.timeIndex, \
                        	minlev=0, maxlev=self.croco.wrapper.N-1, \
                        	lonindex=self.lonIndex,typ=self.variableName)
                
                    elif self.variableName == 'zeta_k':
                        variable[it,1:,:] = get_zetak(self.croco,self.timeIndex, \
                        	minlev=0, maxlev=self.croco.wrapper.N-1, \
                        	lonindex=self.lonIndex)
                
                    elif self.variableName == 'dtdz':
                        variable[it,1:,:] = get_dtdz(self.croco,self.timeIndex, \
                        	minlev=0, maxlev=self.croco.wrapper.N-1, \
                        	lonindex=self.lonIndex)
                
            # Get Latitude coordinates
            x = self.croco.get_coord(self.variableName, direction='y')
            x = repmat(x[:,self.lonIndex].squeeze(),self.croco.wrapper.N,1)
            # Get depths coordinates
            if self.variableName=="u":
                y = np.squeeze(self.croco.wrapper.scoord2z_u(ssh, alpha=0., beta=0, lonindex=self.lonIndex)[:,:,1:])
            elif self.variableName=="v":
                y = np.squeeze(self.croco.wrapper.scoord2z_v(ssh, alpha=0., beta=0, lonindex=self.lonIndex)[:,:,1:-1])
            else :
                y = np.squeeze(self.croco.wrapper.scoord2z_r(ssh, alpha=0., beta=0, lonindex=self.lonIndex)[:,:,1:-1])
            # Create new window
            self.sectionYZ = SectionFrame(\
                croco=self.croco, \
                variableName = self.variableName, \
                variable=variable, 
                x=x, y=y, \
                typSection="YZ" , \
                sliceCoord = self.lon, \
                timeIndex=self.timeIndex)
            # Draw the plot
            self.sectionYZ.updateVariableZ()


# end of class CrocoGui


# Run the program
if __name__ == "__main__":
    app = wx.App(False)
    frame = CrocoGui()
    frame.Show()
    app.MainLoop()