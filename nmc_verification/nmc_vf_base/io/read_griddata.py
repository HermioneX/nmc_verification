#!/usr/bin/python3.6
# -*- coding:UTF-8 -*-
import numpy as np
import os
import math
import xarray as xr
import datetime
import pandas as pd
import traceback
import nmc_verification
import struct
from . import DataBlock_pb2
from .GDS_data_service import GDSDataService
import copy

def grid_ragular(slon,dlon,elon,slat,dlat,elat):
    """
    规范化格点（起始经纬度，间隔经度，格点数）
    :param slon:起始经度
    :param dlon:经度的精度
    :param elon:结束经度
    :param slat:起始纬度
    :param dlat:纬度的精度
    :param elat:结束纬度
    :return:slon1,dlon1,elon1,slat1,dlat1,elat1,nlon1,nlat1
    返回规范化后的格点信息。
    """
    slon1 = slon
    dlon1 = dlon
    elon1 = elon
    slat1 = slat
    dlat1 = dlat
    elat1 = elat
    nlon = 1 + (elon1 - slon1) / dlon1
    error = abs(round(nlon) - nlon)
    if (error > 0.05):
        nlon1 = math.ceil(nlon)
    else:
        nlon1 = int(round(nlon))
    nlat = 1 + (elat - slat) / dlat
    error = abs(round(nlat) - nlat)
    if (error > 0.05):
        nlat1 = math.ceil(nlat)
    else:
        nlat1 = int(round(nlat))
    return slon1,dlon1,elon1,slat1,dlat1,elat1,nlon1,nlat1


def DataArray_to_grd(dataArray,member = None,level = None,time = None,dtime = None,lat = None,lon = None):
    da = copy.deepcopy(dataArray)
    dim_order = {}
    new_coods = {}

    if member is None:
        da  = da.expand_dims("member")
        dim_order["member"] = "member"
        new_coods["member"] = [0]
    elif type(member) == str:
        if member in da.coords:
            dim_order["member"] = member
            new_coods["member"] = da.coords[member]
        else:
            da = da.expand_dims("member")
            dim_order["member"] = "member"
            new_coods["member"] = [0]
    else:
        dim_order["member"] = member.dims[0]
        new_coods["member"] = member.values.tolist()

    if level is None:
        da = da.expand_dims("level")
        dim_order["level"] = "level"
        new_coods["level"] = [0]
    elif type(level) == str:
        if level in da.coords:
            dim_order["level"] = level
            new_coods["level"] = da.coords[level]
        else:
            da = da.expand_dims("level")
            dim_order["level"] = "level"
            new_coods["level"] = [0]
    else:
        dim_order["level"] = level.dims[0]
        new_coods["level"] = level.values.tolist()


    if time is None:
        da = da.expand_dims("time")
        dim_order["time"] = "time"
        new_coods["time"] = pd.date_range("2099-1-1", periods=1)
    elif type(time) == str:
        if time in da.coords:
            dim_order["time"] = time
            new_coods["time"] = da.coords[time]
        else:
            da = da.expand_dims("time")
            dim_order["time"] = "time"
            new_coods["time"] = pd.date_range("2099-1-1", periods=1)
    else:
        dim_order["time"] = time.dims[0]
        new_coods["time"] = time.values.tolist()

    if dtime is None:
        da = da.expand_dims("dtime")
        dim_order["dtime"] = "dtime"
        new_coods["dtime"] = [0]
    elif type(dtime) == str:
        if dtime in da.coords:
            dim_order["dtime"] = dtime
            new_coods["dtime"] = da.coords[dtime]
        else:
            da = da.expand_dims("dtime")
            dim_order["dtime"] = "dtime"
            new_coods["dtime"] = [0]
    else:
        dim_order["level"] = dtime.dims[0]
        new_coods["dtime"] = dtime.values.tolist()

    if lat is None:
        da = da.expand_dims("lat")
        dim_order["lat"] = "latitude"
        new_coods["lat"] = [0]
    elif type(lat) == str:
        if lat in da.coords:
            dim_order["lat"] = lat
            new_coods["lat"] = da.coords[lat]
        else:
            da = da.expand_dims("lat")
            dim_order["lat"] = "latitude"
            new_coods["lat"] = [0]
    else:
        dim_order["lat"] = lat.dims[0]
        new_coods["lat"] = lat.values.tolist()

    if lon is None:
        da = da.expand_dims("lon")
        dim_order["lon"] = "longitude"
        new_coods["lon"] = [0]
    elif type(lon) == str:
        if lon in da.coords:
            dim_order["lon"] = lon
            new_coods["lon"] = da.coords[lon]
        else:
            da = da.expand_dims("lon")
            dim_order["lon"] = "longitude"
            new_coods["lon"] = [0]
    else:
        dim_order["lon"] = lon.dims[0]
        new_coods["lon"] = lon.values.tolist()
    da = da.transpose(dim_order["member"], dim_order["level"], dim_order["time"],
                      dim_order["dtime"], dim_order["lat"], dim_order["lon"])

    da = xr.DataArray(da.values, coords=new_coods, dims=["member","level","time","dtime","latitude","longitude"])
    da.name ="data"
    return da


def read_griddata_from_micaps4(filename,grid=None):
    '''
    读取micaps4格式的格点数据，并将其保存为xarray中DataArray结构的六维数据信息
    :param filename:Micaps4格式的文件路径和文件名
    :param grid:格点的经纬度信息，默认为：None,如果有传入grid信息，需要使用双线性插值进行提取。
    :return:返回一个DataArray结构的六维数据信息da
    '''
    try:
        if not os.path.exists(filename):
            print(filename + " is not exist")
            return None
        try:
            file = open(filename,'r')
            str1 = file.read()
            file.close()
        except:
            file = open(filename,'r',encoding='utf-8')
            str1 = file.read()
            file.close()
        strs = str1.split()
        year1 = int(strs[3])
        month = int(strs[4])
        day = int(strs[5])
        hour = int(strs[6])
        dts = int(strs[7])
        levels = float(strs[8])

        #由于m4只提供年份的后两位，因此，做了个暂时的换算范围在1920-2019年的范围可以匹配成功
        if len(str(year1)) ==4:
            year3 = str(year1)
        else:
            if year1 >= 50:
                year3 = '19' + str(year1)
            else:
                year3 = '20' + str(year1)
        ymd = year3 + "%02d" % month + "%02d" % day + "%02d" % hour + '00'
        dlon = float(strs[9])
        dlat = float(strs[10])
        slon = float(strs[11])
        elon = float(strs[12])
        slat = float(strs[13])
        elat = float(strs[14])
        slon1, dlon1, elon1, slat1, dlat1, elat1, nlon1, nlat1 = grid_ragular(slon,dlon,elon,slat,dlat,elat)
        if len(strs) - 22 >= nlon1 * nlat1 :
            #用户没有输入参数信息的时候，使用m4文件自带的信息
            k = 22
            dat = (np.array(strs[k:])).astype(float).reshape((1, 1, 1, 1, nlat1, nlon1))
            lon = np.arange(nlon1) * dlon1 + slon1
            lat = np.arange(nlat1) * dlat1 + slat1
            dates = pd.to_datetime(ymd, format = "%Y%m%d%H%M" )
            #print(dates)
            #times = pd.date_range(dates, periods=1)
            dtimes = dts
            #print(levels,times,dts)
            da = xr.DataArray(dat, coords={'member': ['data0'], 'level': [levels], 'time': [dates], 'dtime': [dtimes],
                                           'lat': lat, 'lon': lon},
                              dims=['member', 'level', 'time', 'dtime', 'lat', 'lon'])
            da.attrs["dtime_type"] = "hour"
            da.name = "data0"
            nmc_verification.nmc_vf_base.reset(da)
            if grid is None:
                return da
            else:
                #如果传入函数有grid信息，就需要进行一次双线性插值，按照grid信息进行提取网格信息。
                da1 = nmc_verification.nmc_vf_base.interp_gg_linear(da, grid)
                return da1
        else:
            return None
    except (Exception, BaseException) as e:
        exstr = traceback.format_exc()
        print(exstr)
        print(e)
        return None

#读取nc数据
def read_griddata_from_nc(filename,grid = None,value_name = None,member = None,level = None,time = None,dt = None,lat = None,lon = None):

    """
    读取NC文件，并将其保存为xarray中DataArray结构的六维数据信息
    :param filename:NC格式的文件路径和文件名
    :param value_name:nc文件中要素name的值,默认：None
    :param member:要素名,默认：None
    :param level:层次,默认：None
    :param time:时间,默认：None
    :param dt:时效,默认：None
    :param lat:纬度,默认：None
    :param lon:经度,默认：None
    :return:返回一个DataArray结构的六维数据信息da1
    """
    try:
        ds0 = xr.open_dataset(filename)
        drop_list = []
        ds = xr.Dataset()
        #1判断要素成员member
        if(member is None):
            member = "member"
        if member in list(ds0.coords) or member in list(ds0):
            if member in ds0.coords:
                members = ds0.coords[member]
            else:
                members = ds0[member]
                drop_list.append(member)

            ds.coords["member"] = ("member", members)
            attrs_name = list(members.attrs)
            for key in attrs_name:
                ds.member.attrs[key] = members.attrs[key]
        else:
            ds.coords["member"] = ("member", [0])

        #2判断层次level
        if (level is None):
            if "level" in list(ds0.coords) or "level" in list(ds0):
                level = "level"
            elif "lev" in ds0.coords or "lev" in list(ds0):
                level = "lev"
        if level in ds0.coords or level in list(ds0):
            if level in ds0.coords:
                levels = ds0.coords[level]
            else:
                levels = ds0[level]
                drop_list.append(level)
            ds.coords["level"] = ("level", levels)
            attrs_name = list(levels.attrs)
            for key in attrs_name:
                ds.level.attrs[key] = levels.attrs[key]
        else:
            ds.coords["level"] = ("level", [0])

        # 3判断时间time
        if(time is None):
            if "time" in ds0.coords or "time" in list(ds0):
                time = "time"

        if time in ds0.coords or time in list(ds0):
            if time in ds0.coords:
                times = ds0.coords[time]
            else:
                times = ds0[time]
            ds.coords["time"] = ("time", times)
            attrs_name = list(times.attrs)
            for key in attrs_name:
                ds.time.attrs[key] = times.attrs[key]
        else:
            ds.coords["time"] = ("time", [0])

        # 4判断时效dt
        if (dt is None):
            dt = "dtime"
        if dt in ds0.coords or dt in list(ds0):
            if dt in ds0.coords:
                dts = ds0.coords[dt]
            else:
                dts = ds0[dt]
                drop_list.append(dt)

            ds.coords["dtime"] = ("dtime", dts)
            attrs_name = list(dts.attrs)
            for key in attrs_name:
                ds.dt.attrs[key] = dts.attrs[key]
        else:
            ds.coords["dtime"] = ("dtime", [0])

        #5判断纬度lat
        if(lat is None):
            if "latitude" in ds0.coords or "latitude" in list(ds0):
                lat = "latitude"
            elif "lat" in ds0.coords or "lat" in list(ds0):
                lat = "lat"
        if lat in ds0.coords or lat in list(ds0):
            if lat in ds0.coords:
                lats = ds0.coords[lat]
            else:
                lats = ds0[lat]
                drop_list.append(lat)
            dims = lats.dims
            if len(dims) == 1:
                ds.coords["lat"] = ("lat", lats)
            else:
                if "lon" in dims[0].lower() or "x" in dims.lower():
                    lats = lats.values.T
                ds.coords["lat"] = (("lat","lon"), lats)
            attrs_name = list(lats.attrs)
            for key in attrs_name:
                ds.lat.attrs[key] = lats.attrs[key]
        else:
            ds.coords["lat"] = ("lat",[0])

        #6判断经度lon
        if(lon is None):
            if "longitude" in ds0.coords or "longitude" in list(ds0):
                lon = "longitude"
            elif "lon" in ds0.coords or "lon" in list(ds0):
                lon = "lon"
        if lon in ds0.coords or lon in list(ds0):
            if lon in ds0.coords:
                lons = ds0.coords[lon]
            else:
                lons = ds0[lon]
                drop_list.append(lon)

            dims = lons.dims
            if len(dims) == 1:
                ds.coords["lon"] = ("lon", lons)
            else:
                if "lon" in dims[0].lower() or "x" in dims.lower():
                    lons = lons.values.T
                ds.coords["lon"] = (("lat","lon"), lons)
            attrs_name = list(lons.attrs)
            for key in attrs_name:
                ds.lon.attrs[key] = lons.attrs[key]
        else:
            ds.coords["lon"] = ("lon",[0])

        da = None
        if value_name is not None:
            da = ds0[value_name]
            name = value_name
        else:
            name_list = list((ds0))
            for name in name_list:
                if name in drop_list: continue
                da = ds0[name]
                shape = da.values.shape
                size = 1
                for i in range(len(shape)):
                    size = size * shape[i]
                if size > 1:
                    break

        dims = da.dims
        dim_order = {}


        for dim in dims:
            if  "member" in dim.lower():
                dim_order["member"] = dim
            elif dim.lower().find("time") ==0:
                dim_order["time"] = dim
            elif dim.lower().find("dt") ==0:
                dim_order["dtime"] = dim
            elif dim.lower().find("lev") ==0:
                dim_order["level"] = dim
            elif dim.lower().find("lat") ==0 or 'y' == dim.lower():
                dim_order["lat"] = dim
            elif dim.lower().find("lon") ==0 or 'x' == dim.lower():
                dim_order["lon"] = dim


        if "member" not in dim_order.keys():
            dim_order["member"] = "member"
            da = da.expand_dims("member")
        if "time" not in dim_order.keys():
            dim_order["time"] = "time"
            da = da.expand_dims("time")
        if "level" not in dim_order.keys():
            dim_order["level"] = "level"
            da = da.expand_dims("level")
        if "dtime" not in dim_order.keys():
            dim_order["dtime"] = "dtime"
            da = da.expand_dims("dtime")
        if "lat" not in dim_order.keys():
            dim_order["lat"] = "lat"
            da = da.expand_dims("lat")
        if "lon" not in dim_order.keys():
            dim_order["lon"] = "lon"
            da = da .expand_dims("lon")

        #print(da)
        da = da.transpose(dim_order["member"],dim_order["level"],dim_order["time"],
                          dim_order["dtime"],dim_order["lat"],dim_order["lon"])
        #print(name)
        ds[name] = (("member","level","time","dtime","lat","lon"),da)
        attrs_name = list(da.attrs)
        for key in attrs_name:
            ds[name].attrs[key] = da.attrs[key]
        attrs_name = list(ds0.attrs)
        for key in attrs_name:
            ds.attrs[key] = ds0.attrs[key]
        da1 = ds[name]
        da1.name = "data"
        if da1.coords['time'] is None:
            da1.coords['time'] = pd.date_range("2099-1-1",periods=1)
        if da1.coords['dtime'] is None:
            da1.coords['dtime'] = [0]

        attrs_name = list(da1.attrs)
        if "dtime_type" in attrs_name:
            da1.attrs["dtime_type"]= "hour"

        nmc_verification.nmc_vf_base.reset(da1)
        if grid is None:
            da1.name = "data0"
            return da1
        else:
            # 如果传入函数有grid信息，就需要进行一次双线性插值，按照grid信息进行提取网格信息。
            da2 = nmc_verification.nmc_vf_base.interp_gg_linear(da1, grid)
            da2.name = "data0"
            return da2
    except (Exception, BaseException) as e:
        exstr = traceback.format_exc()
        print(exstr)
        print(e)
        return None


#读取nc数据
def read_griddata_from_nc1(filename,grid = None,value_name = None,member = None,level = None,time = None,dt = None,lat = None,lon = None):

    """
    读取NC文件，并将其保存为xarray中DataArray结构的六维数据信息
    :param filename:NC格式的文件路径和文件名
    :param value_name:nc文件中要素name的值,默认：None
    :param member:要素名,默认：None
    :param level:层次,默认：None
    :param time:时间,默认：None
    :param dt:时效,默认：None
    :param lat:纬度,默认：None
    :param lon:经度,默认：None
    :return:返回一个DataArray结构的六维数据信息da1
    """
    try:
        ds0 = xr.open_dataset(filename)
        drop_list = []
        ds = xr.Dataset()
        #1判断要素成员member
        if member in list(ds0):
            drop_list.append(member)
            member =  ds0[member]

        #2判断层次level
        if level in list(ds0):
            drop_list.append(level)
            level = ds0[level]
        #3 time
        if time is None:
            if "time" in ds0.coords or "time" in list(ds0):
                time = "time"
        elif time in list(ds0):
            drop_list.append(time)
            time = ds0[time]

        if dt in list(ds0):
            drop_list.append(dt)
            dt = ds0[dt]

        #5判断纬度lat
        if(lat is None):
            if "latitude" in ds0.coords or "latitude" in list(ds0):
                lat = "latitude"
            elif "lat" in ds0.coords or "lat" in list(ds0):
                lat = "lat"

        if lat in list(ds0):
            drop_list.append(lat)
            lat = ds0[lat]

        #6判断经度lon
        if(lon is None):
            if "longitude" in ds0.coords or "longitude" in list(ds0):
                lon = "longitude"
            elif "lon" in ds0.coords or "lon" in list(ds0):
                lon = "lon"
        if lon in list(ds0):
            drop_list.append(lon)
            lon = ds0[lon]

        da = None
        if value_name is not None:
            da = ds0[value_name]
        else:
            name_list = list((ds0))
            for name in name_list:
                if name in drop_list: continue
                da = ds0[name]
                shape = da.values.shape
                size = 1
                for i in range(len(shape)):
                    size = size * shape[i]
                if size > 1:
                    break
        da1 = DataArray_to_grd(da,member,level,time,dt,lat,lon)

        nmc_verification.nmc_vf_base.reset(da1)
        if grid is None:
            da1.name = "data0"
            return da1
        else:
            # 如果传入函数有grid信息，就需要进行一次双线性插值，按照grid信息进行提取网格信息。
            da2 = nmc_verification.nmc_vf_base.interp_gg_linear(da1, grid)
            da2.name = "data0"
            return da2


    except:
        exstr = traceback.format_exc()
        print(exstr)


def read_griddata_from_gds_file(filename,grid = None):
    try:
        if not os.path.exists(filename):
            print(filename + " is not exist")
            return None
        file = open(filename, 'rb')
        byteArray = file.read()
        discriminator = struct.unpack("4s", byteArray[:4])[0].decode("gb2312")
        t = struct.unpack("h", byteArray[4:6])
        mName = struct.unpack("20s", byteArray[6:26])[0].decode("gb2312")
        eleName = struct.unpack("50s", byteArray[26:76])[0].decode("gb2312")
        description = struct.unpack("30s", byteArray[76:106])[0].decode("gb2312")
        level, y, m, d, h, timezone, period = struct.unpack("fiiiiii", byteArray[106:134])
        startLon, endLon, lonInterval, lonGridCount = struct.unpack("fffi", byteArray[134:150])
        startLat, endLat, latInterval, latGridCount = struct.unpack("fffi", byteArray[150:166])
        isolineStartValue, isolineEndValue, isolineInterval = struct.unpack("fff", byteArray[166:178])
        gridCount = lonGridCount * latGridCount
        description = mName.rstrip('\x00') + '_' + eleName.rstrip('\x00') + "_" + str(
            level) + '(' + description.rstrip('\x00') + ')' + ":" + str(period)
        if (gridCount == (len(byteArray) - 278) / 4):
            if (startLat > 90): startLat = 90.0
            if (startLat < -90): startLat = -90.0
            if (endLat > 90): endLat = 90.0
            if (endLat < -90): endLat = -90.0
            grid0 = nmc_verification.nmc_vf_base.grid([startLon,endLon,lonInterval],[startLat,endLat,latInterval])
            grd = nmc_verification.nmc_vf_base.grid_data(grid0)
            grd.values = np.frombuffer(byteArray[278:], dtype='float32').reshape(1,1,1,1,grid0.nlat, grid0.nlon)
            grd.attrs["dtime_type"] = "hour"
            nmc_verification.nmc_vf_base.reset(grd)
            if (grid is None):
                grd.name = "data0"
                return grd
            else:
                da = nmc_verification.nmc_vf_base.interp_gg_linear(grd, grid)
                da.name = "data0"
                return da
    except Exception as e:
        print(e)
        return None



def read_griddata_from_gds(ip,port,filename,grid = None):
    # ip 为字符串形式，示例 “10.20.30.40”
    # port 为整数形式
    # filename 为字符串形式 示例 "ECMWF_HR/TCDC/19083108.000"

    service = GDSDataService(ip, port)
    try:
        if(service is None):
            print("service is None")
            return
        directory,fileName = os.path.split(filename)
        status, response = service.getData(directory, fileName)
        ByteArrayResult = DataBlock_pb2.ByteArrayResult()
        if status == 200:
            ByteArrayResult.ParseFromString(response)
            if ByteArrayResult is not None:
                byteArray = ByteArrayResult.byteArray
                discriminator = struct.unpack("4s", byteArray[:4])[0].decode("gb2312")
                t = struct.unpack("h", byteArray[4:6])
                mName = struct.unpack("20s", byteArray[6:26])[0].decode("gb2312")
                eleName = struct.unpack("50s", byteArray[26:76])[0].decode("gb2312")
                description = struct.unpack("30s", byteArray[76:106])[0].decode("gb2312")
                level, y, m, d, h, timezone, period = struct.unpack("fiiiiii", byteArray[106:134])
                startLon, endLon, lonInterval, lonGridCount = struct.unpack("fffi", byteArray[134:150])
                startLat, endLat, latInterval, latGridCount = struct.unpack("fffi", byteArray[150:166])
                isolineStartValue, isolineEndValue, isolineInterval = struct.unpack("fff", byteArray[166:178])
                gridCount = lonGridCount * latGridCount
                description = mName.rstrip('\x00') + '_' + eleName.rstrip('\x00') + "_" + str(
                    level) + '(' + description.rstrip('\x00') + ')' + ":" + str(period)
                if (gridCount == (len(byteArray) - 278) / 4):
                    if (startLat > 90): startLat = 90.0
                    if (startLat < -90): startLat = -90.0
                    if (endLat > 90): endLat = 90.0
                    if (endLat < -90): endLat = -90.0
                    grid0 = nmc_verification.nmc_vf_base.grid([startLon, endLon, lonInterval],
                                                              [startLat, endLat, latInterval])
                    grd = nmc_verification.nmc_vf_base.grid_data(grid0)
                    grd.values = np.frombuffer(byteArray[278:], dtype='float32').reshape(1, 1, 1, 1, grid0.nlat,
                                                                                         grid0.nlon)
                    grd.attrs["dtime_type"] = "hour"
                    nmc_verification.nmc_vf_base.reset(grd)
                    if (grid is None):
                        grd.name = "data0"
                        return grd
                    else:
                        da = nmc_verification.nmc_vf_base.interp_gg_linear(grd, grid)
                        da.name = "data0"
                        return da
        elif status == 416:
            print(filename + "超出可读时间")
            return None
    except Exception as e:
        print(e)
        return None


def read_gridwind_from_gds(ip,port,filename,grid = None):
    # ip 为字符串形式，示例 “10.20.30.40”
    # port 为整数形式
    # filename 为字符串形式 示例 "ECMWF_HR/TCDC/19083108.000"

    service = GDSDataService(ip, port)
    try:
        if(service is None):
            print("service is None")
            return
        directory,fileName = os.path.split(filename)
        status, response =  service.getData(directory, fileName)
        ByteArrayResult = DataBlock_pb2.ByteArrayResult()
        if status == 200:
            ByteArrayResult.ParseFromString(response)
            if ByteArrayResult is not None:
                byteArray = ByteArrayResult.byteArray
                discriminator = struct.unpack("4s", byteArray[:4])[0].decode("gb2312")
                t = struct.unpack("h", byteArray[4:6])
                mName = struct.unpack("20s", byteArray[6:26])[0].decode("gb2312")
                eleName = struct.unpack("50s", byteArray[26:76])[0].decode("gb2312")
                description = struct.unpack("30s", byteArray[76:106])[0].decode("gb2312")
                level, y, m, d, h, timezone, period = struct.unpack("fiiiiii", byteArray[106:134])
                startLon, endLon, lonInterval, lonGridCount = struct.unpack("fffi", byteArray[134:150])
                startLat, endLat, latInterval, latGridCount = struct.unpack("fffi", byteArray[150:166])
                isolineStartValue, isolineEndValue, isolineInterval = struct.unpack("fff", byteArray[166:178])
                gridCount = lonGridCount * latGridCount
                description = mName.rstrip('\x00') + '_' + eleName.rstrip('\x00') + "_" + str(
                    level) + '(' + description.rstrip('\x00') + ')' + ":" + str(period)
                if (gridCount == (len(byteArray) - 278) / 8):
                    if (startLat > 90): startLat = 90.0
                    if (startLat < -90): startLat = -90.0
                    if (endLat > 90): endLat = 90.0
                    if (endLat < -90): endLat = -90.0
                    grid0 = nmc_verification.nmc_vf_base.grid([startLon, endLon, lonInterval], [startLat, endLat, latInterval])
                    speed = nmc_verification.nmc_vf_base.grid_data(grid0)
                    i_s = 278
                    i_e = 278 + grid0.nlon * grid0.nlat * 4
                    speed.values = np.frombuffer(byteArray[i_s:i_e], dtype='float32').reshape(1, 1, 1, 1, grid0.nlat, grid0.nlon)
                    i_s += grid0.nlon * grid0.nlat * 4
                    i_e += grid0.nlon * grid0.nlat * 4
                    angle = nmc_verification.nmc_vf_base.grid_data(grid0)
                    angle.values = np.frombuffer(byteArray[i_s:i_e], dtype='float32').reshape(1, 1, 1, 1, grid0.nlat, grid0.nlon)
                    nmc_verification.nmc_vf_base.reset(speed)
                    nmc_verification.nmc_vf_base.reset(angle)

                    wind = nmc_verification.nmc_vf_base.diag.speed_angle_to_wind(speed, angle)
                    if (grid is None):
                        return wind
                    else:
                        return nmc_verification.nmc_vf_base.interp_gg_linear(wind, grid)

    except Exception as e:
        print(e)
        return None


def read_gridwind_from_gds_file(filename,grid = None):
    try:
        if not os.path.exists(filename):
            print(filename + " is not exist")
            return None
        file = open(filename, 'rb')
        byteArray = file.read()
        #print(len(byteArray))
        discriminator = struct.unpack("4s", byteArray[:4])[0].decode("gb2312")
        t = struct.unpack("h", byteArray[4:6])
        mName = struct.unpack("20s", byteArray[6:26])[0].decode("gb2312")
        eleName = struct.unpack("50s", byteArray[26:76])[0].decode("gb2312")
        description = struct.unpack("30s", byteArray[76:106])[0].decode("gb2312")
        level, y, m, d, h, timezone, period = struct.unpack("fiiiiii", byteArray[106:134])
        startLon, endLon, lonInterval, lonGridCount = struct.unpack("fffi", byteArray[134:150])
        startLat, endLat, latInterval, latGridCount = struct.unpack("fffi", byteArray[150:166])
        isolineStartValue, isolineEndValue, isolineInterval = struct.unpack("fff", byteArray[166:178])
        gridCount = lonGridCount * latGridCount
        description = mName.rstrip('\x00') + '_' + eleName.rstrip('\x00') + "_" + str(
            level) + '(' + description.rstrip('\x00') + ')' + ":" + str(period)
        if (gridCount == (len(byteArray) - 278) / 8):
            if(startLat > 90):startLat = 90.0
            if(startLat < -90) : startLat = -90.0
            if(endLat > 90) : endLat = 90.0
            if(endLat < -90): endLat = -90.0
            grid0 = nmc_verification.nmc_vf_base.grid([startLon,endLon,lonInterval],[startLat,endLat,latInterval])
            speed = nmc_verification.nmc_vf_base.grid_data(grid0)
            i_s = 278
            i_e = 278 + grid0.nlon * grid0.nlat *4
            speed.values = np.frombuffer(byteArray[i_s:i_e], dtype='float32').reshape(1,1,1,1,grid0.nlat,grid0.nlon)
            i_s += grid0.nlon * grid0.nlat *4
            i_e += grid0.nlon * grid0.nlat *4
            angle = nmc_verification.nmc_vf_base.grid_data(grid0)
            angle.values = np.frombuffer(byteArray[i_s:i_e], dtype='float32').reshape(1,1,1,1,grid0.nlat, grid0.nlon)
            nmc_verification.nmc_vf_base.reset(speed)
            nmc_verification.nmc_vf_base.reset(angle)

            wind = nmc_verification.nmc_vf_base.diag.speed_angle_to_wind(speed,angle)
            if (grid is None):
                return wind
            else:
                return nmc_verification.nmc_vf_base.diag.interp_gg_linear(wind,grid)

    except Exception as e:
        print(e)
        return None

def read_gridwind_from_micaps2(filename,grid = None):
    if os.path.exists(filename):
        try:
            column = nmc_verification.nmc_vf_base.m2_element_column.风向
            sta_angle = nmc_verification.nmc_vf_base.io.read_stadata_from_micaps1_2_8(filename,column,drop_same_id=False)
            column = nmc_verification.nmc_vf_base.m2_element_column.风速
            sta_speed = nmc_verification.nmc_vf_base.io.read_stadata_from_micaps1_2_8(filename, column,drop_same_id=False)
            grid_angle = nmc_verification.nmc_vf_base.trans_sta_to_grd(sta_angle)
            grid_angle.values = 270 - grid_angle.values
            grid_speed = nmc_verification.nmc_vf_base.trans_sta_to_grd(sta_speed)
            wind = nmc_verification.nmc_vf_base.diag.speed_angle_to_wind(grid_speed,grid_angle)
            nmc_verification.nmc_vf_base.reset(wind)
            if grid is None:
                return wind
            else:
                wind1 = nmc_verification.nmc_vf_base.interp_gg_linear(wind,grid=grid)
                return wind1
        except (Exception, BaseException) as e:
            exstr = traceback.format_exc()
            print(exstr)
            print(e)
            return None
    else:
        print(filename + " not exists")
        return None

def read_gridwind_from_micaps11(filename,grid = None):
    if os.path.exists(filename):
        file = open(filename, 'r')
        str1 = file.read()
        file.close()
        strs = str1.split()
        dlon = float(strs[8])
        dlat = float(strs[9])
        slon = float(strs[10])
        elon = float(strs[11])
        slat = float(strs[12])
        elat = float(strs[13])
        grid0 =nmc_verification.nmc_vf_base.grid([slon,elon,dlon],[slat,elat,dlat])
        if len(strs) - 15 >= 2 * grid0.nlon * grid0.nlat:
            k = 16
            dat_u= (np.array(strs[k:(k + grid0.nlon * grid0.nlat)])).astype(float).reshape((grid0.nlat,grid0.nlon))
            k += grid0.nlon * grid0.nlat
            dat_v = (np.array(strs[k:(k + grid0.nlon * grid0.nlat)])).astype(float).reshape((grid0.nlat, grid0.nlon))
            grid_u = nmc_verification.nmc_vf_base.grid_data(grid0,dat_u)
            grid_v = nmc_verification.nmc_vf_base.grid_data(grid0,dat_v)
            wind = nmc_verification.nmc_vf_base.diag.u_v_to_wind(grid_u,grid_v)
            nmc_verification.nmc_vf_base.reset(wind)
            if grid is None:
                return wind
            else:
                wind1 = nmc_verification.nmc_vf_base.interp_gg_linear(wind, grid=grid)
                return wind1
        else:
            print(filename + " format wrong")
            return None
    else:
        print(filename + " not exists")
        return None


def read_AWX_from_gds(ip,port,filename,grid = None):
    # ip 为字符串形式，示例 “10.20.30.40”
    # port 为整数形式
    # filename 为字符串形式 示例 "ECMWF_HR/TCDC/19083108.000"

    service = GDSDataService(ip, port)
    try:
        if(service is None):
            print("service is None")
            return
        directory,fileName = os.path.split(filename)
        status, response = byteArrayResult = service.getData(directory, fileName)
        ByteArrayResult = DataBlock_pb2.ByteArrayResult()
        if status == 200:
            ByteArrayResult.ParseFromString(response)
            if ByteArrayResult is not None:
                byteArray = ByteArrayResult.byteArray
                sat96 = struct.unpack("12s", byteArray[:12])[0]
                levl = np.frombuffer(byteArray[12:30], dtype='int16').astype(dtype="int32")
                formatstr = struct.unpack("8s", byteArray[30:38])[0]
                qualityflag = struct.unpack("h", byteArray[38:40])[0]
                satellite = struct.unpack("8s", byteArray[40:48])[0]
                lev2 = np.frombuffer(byteArray[48:104], dtype='int16').astype(dtype="int32")

                recordlen = levl[4]
                headnum = levl[5]
                datanum = levl[6]
                timenum = lev2[0:5]
                nlon = lev2[7]
                nlat = lev2[8]
                range = lev2[12:16].astype("float32")
                slat = range[0] / 100
                elat = range[1] / 100
                slon = range[2] / 100
                elon = range[3] / 100

                # nintels=lev2[20:22].astype("float32")
                dlon = (elon - slon) / (nlon - 1)
                dlat = (elat - slat) / (nlat - 1)

                colorlen = lev2[24]
                caliblen = lev2[25]
                geololen = lev2[26]

                # print(levl)
                # print(lev2)
                head_lenght = headnum * recordlen
                data_lenght = datanum * recordlen
                # print(head_lenght  + data_lenght)
                # print( data_lenght)
                # print(grd.nlon * grd.nlat)
                # headrest = np.frombuffer(byteArray[:head_lenght], dtype='int8')
                data_awx = np.frombuffer(byteArray[head_lenght:(head_lenght + data_lenght)], dtype='int8')

                if colorlen <= 0:
                    calib = np.frombuffer(byteArray[104:(104 + 2048)], dtype='int16').astype(dtype="float32")
                else:
                    # color = np.frombuffer(byteArray[104:(104+colorlen*2)], dtype='int16')
                    calib = np.frombuffer(byteArray[(104 + colorlen * 2):(104 + colorlen * 2 + 2048)],
                                          dtype='int16').astype(
                        dtype="float32")

                realcalib = calib / 100.0
                realcalib[calib < 0] = (calib[calib < 0] + 65536) / 100.0

                awx_index = np.empty(len(data_awx), dtype="int32")
                awx_index[:] = data_awx[:]
                awx_index[data_awx < 0] = data_awx[data_awx < 0] + 256
                awx_index *= 4
                real_data_awx = realcalib[awx_index]
                grid0 = nmc_verification.nmc_vf_base.grid([slon, elon, dlon],[slat, elat, dlat])
                grd = nmc_verification.nmc_vf_base.grid_data(grid0)
                grd.values = real_data_awx.reshape(1,1,1,1,grid0.nlat, grid0.nlon)
                grd.attrs["dtime_type"] = "hour"
                nmc_verification.nmc_vf_base.reset(grd)
                if (grid is None):
                    grd.name = "data0"
                    return grd
                else:
                    da = nmc_verification.nmc_vf_base.function.gxy_gxy.interpolation_linear(grd, grid)
                    da.name = "data0"
                    return da
    except Exception as e:
        print(e)
        return None

def read_griddata_from_binary(filename,grid = None):
    try:
        if not os.path.exists(filename):
            print(filename + " is not exist")
            return None
        file = open(filename, 'rb')
        bytes = file.read()
        file.close()
        head = np.frombuffer(bytes[0:24], dtype='float32')
        grid0 = nmc_verification.nmc_vf_base.grid([head[0],head[1],head[2]],[head[3],head[4],head[5]])
        dat  = np.frombuffer(bytes[24:], dtype='float32')
        grd = nmc_verification.nmc_vf_base.grid_data(grid0,dat)
        return grd
    except Exception as e:
        print(e)
        return None
