#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2009-2019 Satpy developers
#
# This file is part of satpy.
#
# satpy is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# satpy is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# satpy.  If not, see <http://www.gnu.org/licenses/>.
"""Reading and calibrating GAC and LAC AVHRR data.

.. todo::

    Fine grained calibration
    Radiance output

"""

import logging
from datetime import datetime, timedelta

import dask.array as da
import numpy as np
import pygac.utils
import xarray as xr

from satpy import CHUNK_SIZE
from satpy.readers.file_handlers import BaseFileHandler

logger = logging.getLogger(__name__)


class VGACFileHandler(BaseFileHandler):
    """Reader VGAC data."""

    def __init__(self, filename, filename_info, filetype_info, **reader_kwargs):
        """Init the file handler.

        Args:
            reader_kwargs: More keyword arguments to be passed to pygac.Reader.
                See the pygac documentation for available options.

        """
        super(VGACFileHandler, self).__init__(
            filename, filename_info, filetype_info)

        self.engine = "h5netcdf"
        self.reader_kwargs = reader_kwargs
        self._start_time = filename_info['start_time']
        self._end_time = None
        self.sensor = 'viirs'
        self.filename_info = filename_info

    def convert_to_bt(self, data, data_lut, scale_factor):   
        from scipy import interpolate
        x = np.arange(0, len(data_lut))
        y = data_lut
        func = interpolate.interp1d(x,y)
        brightness_temperatures = func(data.values / scale_factor)
        return brightness_temperatures
        
    def get_dataset(self, key, yaml_info):
        """Get dataset."""
        logger.debug("Getting data for: %s", yaml_info['name'])
        nc = xr.open_dataset(self.filename, engine=self.engine, decode_times=False,
                             chunks={'y': CHUNK_SIZE, 'x': CHUNK_SIZE})
        name = yaml_info.get('nc_store_name', yaml_info['name'])
        file_key = yaml_info.get('nc_key', name)
        data = nc[file_key]
        scale_factor = yaml_info.get("scale_factor_nc", 0.0002)
        if file_key + "_LUT" in nc:
            data.data = self.convert_to_bt(data, nc[file_key + "_LUT"], scale_factor)
        if name != yaml_info['name']:
            data = data.rename(yaml_info['name'])
        data.attrs.update(nc.attrs)  # For now add global attributes to all datasets
        data.attrs.update(yaml_info)
        if "StartTime" in data.attrs:
            data.attrs["start_time"] = datetime.strptime(data.attrs["StartTime"], "%Y-%m-%dT%H:%M:%S")
            data.attrs["end_time"] = datetime.strptime(data.attrs["EndTime"], "%Y-%m-%dT%H:%M:%S")
            self._end_time =  data.attrs["end_time"]  
        return data

    def _update_attrs(self, res):
        """Update dataset attributes."""
        for attr in self.reader.meta_data:
            res.attrs[attr] = self.reader.meta_data[attr]
        res.attrs['platform_name'] = self.reader.spacecraft_name
        res.attrs['orbit_number'] = self.filename_info.get('orbit_number', None)
        res.attrs['sensor'] = self.sensor
        try:
            res.attrs['orbital_parameters'] = {'tle': self.reader.get_tle_lines()}
        except (IndexError, RuntimeError):
            pass

    @property
    def start_time(self):
        """Get the start time."""
        return self._start_time

    @property
    def end_time(self):
        """Get the end time."""
        return self._end_time
