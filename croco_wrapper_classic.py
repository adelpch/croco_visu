# -*- coding: UTF-8 -*-
#

import sys
import os
import time
import numpy as np
import netCDF4 as netcdf
import matplotlib.pyplot as plt
from io_xarray import return_xarray_dataarray, return_xarray_dataset

second2day = 1. /86400.

path = "./"
keymap_files = {
    'coordinate_file' : path+"Go_Meddy_his.nc",
    'metric_file' : path+"Go_Meddy_his.nc",
    'mask_file' : path+"Go_Meddy_his.nc",
    'variable_file' : path+"Go_Meddy_his.nc" 
}

keymap_dimensions = {
    'xi_rho': 'x_r',
    'eta_rho': 'y_r',
    'xi_u': 'x_u',
    'eta_v': 'y_v',
    's_rho': 'z_r',
    's_w': 'z_w',
    'time': 't'
}


keymap_coordinates = {
	'x_rho':'lon_r' ,
	'y_rho':'lat_r' ,
	'scrum_time':'time' 
	}


keymap_variables = {
    'zeta': 'ssh'
}

keymap_metrics = {
	'pm':'dx_r',
	'pn':'dy_r',
	'theta_s': 'theta_s',
	'theta_b': 'theta_b',
	# 'Tcline': 'tcline' ,
	'Vtransform': 'scoord' ,
	'hc': 'hc',
	'h': 'h',
	'f': 'f'
	}

keymap_masks = {
    'mask_rho': 'mask_r'
}

#==================== Variables holders for croco ===============================
#

class CrocoWrapper(object):
    """This class create the dictionnary of variables used for creating a
    generic grid from xios croco output files.
    """
    def __init__(self, chunks=None, mask_level=0):

        self.keymap_files = keymap_files
        self.keymap_dimensions=keymap_dimensions
        self.keymap_coordinates=keymap_coordinates
        self.keymap_variables=keymap_variables
        self.keymap_metrics=keymap_metrics
        self.keymap_masks=keymap_masks

        self.chunks = chunks
        self.mask_level = mask_level
        self.coords = {}
        self.metrics = {}
        self.masks = {}

        self.define_coordinates()
        self.define_dimensions(self.dscoord)
        self.define_metrics()
        self.define_masks()
        self.define_variables()
        self.parameters = {}
        self.parameters['chunks'] = chunks


    def _get(self,*args,**kwargs):
        return return_xarray_dataarray(*args,**kwargs)

    def _get_date(self,tindex):
    	return self.coords['time'].values[tindex]

    def change_dimensions(self,ds):
        for key,val in self.keymap_dimensions.items():
            try:
                ds = ds.rename({key:val})
            except:
                pass
        return ds

    def change_coords(self,ds):
        for key,val in self.keymap_coordinates.items():
            try:
                ds = ds.rename({key:val})
            except:
                pass
        return ds

    def change_variables(self,ds):
        for key,val in self.keymap_variables.items():
            try:
                ds = ds.rename({key:val})
            except:
                pass    
        return ds

    def change_metrics(self,ds):
        for key,val in self.keymap_metrics.items():
            try:
                ds = ds.rename({key:val}) 
            except:
                ds.attrs[key] = ds.attrs.pop(val)   	
        return ds

    def change_mask(self,ds):
        for key,val in self.keymap_masks.items():
            try:
                ds = ds.rename({key:val})
            except:
                pass    	
        return ds

    def define_dimensions(self,ds):
    	self.L = ds.dims['x_r']
    	self.M = ds.dims['y_r']
    	self.N = ds.dims['z_r']
    	self.ntimes = ds.dims['t']

    def define_coordinates(self):
        ds = return_xarray_dataset(self.keymap_files['coordinate_file'])
        ds = self.change_dimensions(ds)
        ds = self.change_coords(ds)
        self.dscoord = ds
        lon_r = self._get(self.dscoord,'lon_r',chunks=self.chunks,decode_times=False).values
        lat_r = self._get(self.dscoord,'lat_r',chunks=self.chunks,decode_times=False).values
        self.coords['lon_r'] = lon_r
        self.coords['lat_r'] = lat_r
        self.coords['lon_u'] = 0.5*(lon_r[:,:-1]+lon_r[:,1:])
        self.coords['lat_u'] = 0.5*(lat_r[:,:-1]+lat_r[:,1:])
        self.coords['lon_v'] = 0.5*(lon_r[:-1,:]+lon_r[1:,:])
        self.coords['lat_v'] = 0.5*(lat_r[:-1,:]+lat_r[1:,:])
        self.coords['lon_w'] =lon_r
        self.coords['lat_w'] =lat_r

        # time = time - time_origin
        self.coords['time'] = self._get(self.dscoord,'time',chunks=self.chunks,decode_times=False)
        self.coords['time'] = self.coords['time'] * second2day
        # self.coords['time'].values=np.array(self.coords['time'], dtype='datetime64[D]') - \
        #     np.array(self.coords['time'].time_origin, dtype='datetime64[D]')
        # self.coords['time'].values=	self.coords['time'].values / np.timedelta64(1, 'D')

    def define_metrics(self):
    	ds = return_xarray_dataset(self.keymap_files['metric_file'])
    	ds = self.change_dimensions(ds)
    	ds = self.change_coords(ds)
    	ds = self.change_metrics(ds)
    	self.dsmetrics = ds
    	for key,val in self.keymap_metrics.items():
        	   self.metrics[val] = self._get(self.dsmetrics,val,chunks=self.chunks)


    def define_masks(self):
    	ds = return_xarray_dataset(self.keymap_files['mask_file'])
    	ds = self.change_dimensions(ds)
    	ds = self.change_coords(ds)
    	ds = self.change_mask(ds)
    	self.dsmask = ds
    	for key,val in self.keymap_masks.items():
            try:
                self.masks[val] = self._get(self.dsmask,val,chunks=self.chunks)
            except:
                mask_rho = np.ones_like(self.coords['lon_r'])
                self.masks[val] = xr.DataArray(data=mask_rho)
            self.masks[val] = np.where(self.masks[val]==0.,np.nan,self.masks[val])

    def define_variables(self):
    	ds = return_xarray_dataset(self.keymap_files['variable_file'])
    	ds = self.change_dimensions(ds)
    	ds = self.change_coords(ds)
        ds = self.change_variables(ds)
    	self.dsvar = ds

    def chunk(self,chunks=None):
        """
        Chunk all the variables.
        Parameters
        ----------
        chunks : dict-like
            dictionnary of sizes of chunk along xarray dimensions.
        """
        for dataname in self.variables:
            data = self.variables[dataname]
            if isinstance(data, xr.DataArray):
                self.variables[dataname] = data.chunk(chunks)



    def _scoord2z(self, point_type, ssh, alpha, beta, lonindex=None, latindex=None):
        """
        scoord2z finds z at either rho or w points (positive up, zero at rest surface)
        h          = array of depths (e.g., from grd file)
        theta_s    = surface focusing parameter
        theta_b    = bottom focusing parameter
        hc         = critical depth
        N          = number of vertical rho-points
        point_type = 'r' or 'w'
        scoord     = 'new2008' :new scoord 2008, 'new2006' : new scoord 2006,
                      or 'old1994' for Song scoord
        ssh       = sea surface height
        message    = set to False if don't want message
        """
        def CSF(sc, theta_s, theta_b):
            '''
            Allows use of theta_b > 0 (July 2009)
            '''
            one64 = np.float64(1)

            if theta_s > 0.:
                csrf = ((one64 - np.cosh(theta_s * sc))
                           / (np.cosh(theta_s) - one64))
            else:
                csrf = -sc ** 2
            sc1 = csrf + one64
            if theta_b > 0.:
                Cs = ((np.exp(theta_b * sc1) - one64)
                    / (np.exp(theta_b) - one64) - one64)
            else:
                Cs = csrf
            return Cs
        #
        try:
            self.scoord
        except:
            self.scoord = 2
        N = np.float64(self.N)
        try:
            theta_s = self.metrics['theta_s'].values
        except:
            theta_s = self.metrics['theta_s']
        try:
            theta_b = self.metrics['theta_b'].values
        except:
            theta_b = self.metrics['theta_b']
        try:
            hc = self.metrics['hc'].values
        except:
            hc = self.metrics['hc']
        if lonindex is not None:
            h = self.metrics['h'].values[:,lonindex-1:lonindex+2]
        elif latindex is not None:
            h = self.metrics['h'].values[latindex-1:latindex+2,:]
        else:
            h = self.metrics['h'].values
        scoord = self.metrics['scoord'].values

        sc_w = (np.arange(N + 1, dtype=np.float64) - N) / N
        sc_r = ((np.arange(1, N + 1, dtype=np.float64)) - N - 0.5) / N
        
        if 'w' in point_type:
            sc = sc_w
            N += 1. # add a level
        else:
            sc = sc_r

        z  = np.empty((int(N),) + h.shape, dtype=np.float64)
        if scoord == 2:
            Cs = CSF(sc, theta_s, theta_b)
        else:
            try:
                cff1=1./sinh(theta_s)
                cff2=0.5/tanh(0.5*theta_s)
            except:
                cff1=0.
                cff2=0.
            Cs=(1.-theta_b)*cff1*sinh(theta_s*sc) \
                +theta_b*(cff2*tanh(theta_s*(sc+0.5))-0.5)

        if scoord == 2:
            hinv = 1. / (h + hc)
            cff = (hc * sc).squeeze()
            cff1 = (Cs).squeeze()
            for k in np.arange(N, dtype=int):
                z[k] = ssh + (ssh + h) * (cff[k] + cff1[k] * h) * hinv
        elif scoord == 1:
            hinv = 1. / h
            cff  = (hc * (sc[:] - Cs[:])).squeeze()
            cff1 = Cs.squeeze()
            cff2 = (sc + 1).squeeze()
            for k in np.arange(N, dtype=int) + 1:
                z0      = cff[k-1] + cff1[k-1] * h
                z[k-1, :] = z0 + ssh * (1. + z0 * hinv)
        else:
            raise Exception("Unknown scoord, should be 1 or 2")
        return z.squeeze(), np.float32(Cs)

    def scoord2z_r(self, ssh=0., alpha=0., beta=1., lonindex=None, latindex=None):
        '''
        Depths at rho point
        '''
        return self._scoord2z('r', ssh=ssh, alpha=alpha, beta=beta, \
            lonindex=lonindex, latindex=latindex)[0]


    def scoord2z_u(self, ssh=0., alpha=0., beta=1., lonindex=None, latindex=None):
        '''
        Depths at u point
        '''
        depth = self._scoord2z('r', ssh=ssh, alpha=alpha, beta=beta, \
            lonindex=lonindex, latindex=latindex)[0]
        return 0.5*(depth[:,:,:-1]+depth[:,:,1:])

    def scoord2z_v(self, ssh=0., alpha=0., beta=1., lonindex=None, latindex=None):
        '''
        Depths at v point
        '''
        depth = self._scoord2z('r', ssh=ssh, alpha=alpha, beta=beta, \
            lonindex=lonindex, latindex=latindex)[0]
        return 0.5*(depth[:,:-1,:]+depth[:,1:,:])

    def scoord2dz_r(self, ssh=0., alpha=0., beta=1., lonindex=None, latindex=None):
        """
        dz at rho points, 3d matrix
        """
        dz = self._scoord2z('w', ssh=ssh, alpha=alpha, beta=beta, \
            lonindex=lonindex, latindex=latindex)[0]
        return dz[1:] - dz[:-1]

    def scoord2dz_u(self, ssh=0., alpha=0., beta=1., lonindex=None, latindex=None):
        '''
        dz at u points, 3d matrix
        '''
        dz = self.scoord2dz(ssh=ssh, alpha=0., beta=1., \
            lonindex=lonindex, latindex=latindex)
        return 0.5*(dz[:,:,:-1]+dz[:,:,1:])

    def scoord2dz_v(self, ssh=0., alpha=0., beta=1., lonindex=None, latindex=None):
        '''
        dz at v points
        '''
        dz = self.scoord2dz(ssh=ssh, alpha=0., beta=1., \
            lonindex=lonindex, latindex=latindex)
        return 0.5*(dz[:,:-1,:]+dz[:,1:,:])

# Run the program
if __name__ == "__main__":
    croco = CrocoWrapper(coordinate_file="moz_his.nc",mask_file="moz_his.nc" )