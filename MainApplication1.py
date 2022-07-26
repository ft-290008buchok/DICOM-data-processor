#This code is not a commercial product and is written for educational purposes
import numpy as np
import math
import os
import glob
import matplotlib.pyplot as plt
import pydicom
from pydicom.uid import RLELossless
import pydicom.data
from pydicom.fileset import FileSet

def loadFiles():
    '''
    A 3d dicom model converted into a numpy array, 
    a binary 3d mask of a segmented formation and 
    one dcm file from a folder with dicom snapshots are loaded
    '''
    arterial = np.load('arterial.npy')
    maskZip = np.load('segmentationseg.npz')
    mask = maskZip['arr_0']
    images = glob.glob('./28_02_2021_14_35_06/*.dcm')
    ds = pydicom.dcmread(images[0])
    return [arterial, mask, ds]

def calcDensityParams(arterial, mask):
    '''
    each voxel has a density value, characterizing a point in 3d space, 
    mean is the arithmetic mean of the formation density, 
    median is the central value from a series of sorted density values, 
    std is the standard deviation
    '''
    arterial -= 1000
    #apply a mask
    arterial = arterial * mask

    mean = np.mean(arterial[arterial > 0])
    median = np.median(arterial[arterial > 0])
    std = np.std(arterial[arterial > 0])

    return [mean, median, std]

def calcMaxValues(mask, ds):
    '''
    dimensions of a parallelepiped 
    oriented along the coordinate axes 
    described around the formation
    '''
    z = 0
    for i in range(len(mask)):
        if len(np.flatnonzero(mask[i])) > 0:
            z += 1
    z = z * ds.SliceThickness

    x = 0
    mx = np.moveaxis(mask, 2, 0)
    for i in range(len(mx)):
        if len(np.flatnonzero(mx[i])) > 0:
            x += 1
    x = x * ds.PixelSpacing[0]

    y = 0
    my = np.moveaxis(mask, 0, 1)
    for i in range(len(my)):
        if len(np.flatnonzero(my[i])) > 0:
            y += 1
    y = y * ds.PixelSpacing[0]
    
    return [x, y, z]

def calcVolume(mask, ds):
    '''
    the volume of each slice of the formation 
    and the total volume are calculated
    '''
    deltaS = ds.PixelSpacing[0] * ds.PixelSpacing[0]
    V = 0
    for i in range(len(mask)):
        ones = len(np.flatnonzero(mask[i]))
        if ones > 0:
            V += ones * deltaS
    V = V * ds.SliceThickness
    V = V / 1000
    return V

#Nhis code was copied from https://github.com/AIM-Harvard/pyradiomics/blob/master/radiomics/shape.py
def majorMinorFromPyradiomics(mask, ds):
    '''
    the major and minor lengths of the formation are calculated
    '''
    labelledVoxelCoordinates = np.where(mask != 0)
    Np = len(labelledVoxelCoordinates[0])
    coordinates = np.array(labelledVoxelCoordinates, dtype='int').transpose((1, 0))
    physicalCoordinates = coordinates * ds.PixelSpacing[0]
    physicalCoordinates -= np.mean(physicalCoordinates, axis=0) 
    physicalCoordinates /= np.sqrt(Np)
    covariance = np.dot(physicalCoordinates.T.copy(), physicalCoordinates)
    eigenValues = np.linalg.eigvals(covariance)

    machine_errors = np.bitwise_and(eigenValues < 0, eigenValues > -1e-10)
    if np.sum(machine_errors) > 0:
      eigenValues[machine_errors] = 0

    eigenValues.sort()

    if eigenValues[2] < 0:
      return np.nan
    major = np.sqrt(eigenValues[2]) * 4

    if eigenValues[1] < 0:
      return np.nan
    minor = np.sqrt(eigenValues[1]) * 4
    return[major, minor]

#these are utility functions for calcSphereRadius
def calcUpperLen(nask, ds):
    for i in range(len(mask)):
        if len(np.flatnonzero(mask[i])) > 0:
            return i * ds.SliceThickness

def calcLeftLen(mask, ds):
    mx = np.moveaxis(mask, 2, 0)
    for i in range(len(mx)):
        if len(np.flatnonzero(mx[i])) > 0:
            return i * ds.PixelSpacing[0]

def calcBackLen(mask, ds):
    my = np.moveaxis(mask, 0, 1)
    for i in range(len(my)):
        if len(np.flatnonzero(my[i])) > 0:
            return i * ds.PixelSpacing[0]

def calcSphereRadius(mask, ds, x, y, z):
    '''
    the radius of the sphere described around the formation is calculated
    the function takes a binary mask of the formation, one dicom snapshot and 
    the dimensions of the parallelepiped oriented along the coordinate axes described around the formation, 
    to find them you can use calcMaxValues()
    '''
    #extraction of physical coordinates of points of formation
    labelledVoxelCoordinates = np.where(mask != 0)
    coordinates = np.array(labelledVoxelCoordinates, dtype='int').transpose((1, 0))
    physicalCoordinates = coordinates * np.array((ds.SliceThickness, ds.PixelSpacing[0], ds.PixelSpacing[0]))

    #move physicalCoordinates to the coordinate system centre
    #physicalCoordinates appraisement
    xL = calcLeftLen(mask, ds)
    yL = calcBackLen(mask, ds)
    zL = calcUpperLen(mask, ds)
    physicalCoordinates -= np.array((zL, yL, xL))
    physicalCoordinates -= np.array((z / 2, y / 2, x / 2))

    #calculation of distances from the center of formation to all points of formation
    #center here is the center of the parallelepiped oriented along the coordinate axes described around the formation
    quadroCoordintaes = np.multiply(physicalCoordinates, physicalCoordinates)
    quadroDistances =  np.sum(quadroCoordintaes, axis = 1)
    distances = np.sqrt(quadroDistances)

    #the point as far as possible from the center is taken as the sphere radius
    ind = distances.argmax()
    
    return distances[ind]

def getExternalPoints(mask):
    '''
    Extracting voxel-coordinates the extreme points (surface) of a 
    three-dimensional binary mask of an object
    '''
    mx = np.copy(mask)
    mx = np.moveaxis(mx, 2, 0)
    mz = np.copy(mask)
    mz = np.moveaxis(mz, 0, 2)

    for i in range(len(mask)):
        for j in range(len(mask[i])):
            points = np.flatnonzero(mask[i][j])
            pointsNum = len(points)
            if pointsNum > 0:
                mask[i][j] *= 0
                mask[i][j][points[0]] = 1
                mask[i][j][points[pointsNum - 1]] = 1
    
    for i in range(len(mx)):
        for j in range(len(mx[i])):
            points = np.flatnonzero(mx[i][j])
            pointsNum = len(points)
            if pointsNum > 0:
                mask[j][points[0]][i] = 1
                mask[j][points[pointsNum - 1]][i] = 1

    for i in range(len(mz)):
        for j in range(len(mz[i])):
            points = np.flatnonzero(mz[i][j])
            pointsNum = len(points)
            if pointsNum > 0:
                mask[points[pointsNum - 1]][i][j] = 1
                mask[points[0]][i][j] = 1

    labelledVoxelCoordinates = np.where(mask != 0)
    coordinates = np.array(labelledVoxelCoordinates, dtype='int').transpose((1, 0))

    #show surface in 2 projections
    #plt.imshow(mask[650], cmap=plt.cm.bone)
    #plt.show()

    #mask = np.moveaxis(mask, 2, 0)
    #plt.imshow(mask[200], cmap=plt.cm.bone)
    #plt.show()

    return coordinates

def calcMaxRemotedPoints(surface, ds):
    '''
    Extracting voxel coordinates of the most remote points 
    and distance between them
    Function gets numPy-array of surface voxel-coordinates of the formation
    (to find them you can use getExternalPoints()) and one dcm file
    
    '''
    realCoordinates = np.copy(surface)
    physicalCoordinates = surface * np.array((ds.SliceThickness, ds.PixelSpacing[0], ds.PixelSpacing[0]))
    
    xL = calcLeftLen(mask, ds)
    yL = calcBackLen(mask, ds)
    zL = calcUpperLen(mask, ds)
    physicalCoordinates -= np.array((zL, yL, xL))
    physicalCoordinates -= np.array((z / 2, y / 2, x / 2))

    moovedCoordinates = np.copy(physicalCoordinates)

    quadroCoordintaes = np.multiply(physicalCoordinates, physicalCoordinates)
    quadroDistances =  np.sum(quadroCoordintaes, axis = 1)
    distances = np.sqrt(quadroDistances)

    ind = distances.argmax()

    moovedCoordinates -= moovedCoordinates[ind]
    quadroCoordintaes = np.multiply(moovedCoordinates, moovedCoordinates)
    quadroDistances =  np.sum(quadroCoordintaes, axis = 1)
    distances = np.sqrt(quadroDistances)

    ind1 = distances.argmax()
    return [realCoordinates[ind], realCoordinates[ind1], distances[ind1]]

    
#examples
#-------------------------------------
arterial, mask, ds = loadFiles()
mean, median, std = calcDensityParams(arterial, mask)

print('mean density value = ', mean)
print('median density value = ', median)
print('std density value = ', std)
print('----------------------------------')

x, y, z = calcMaxValues(mask, ds)

print('x-max = ', x, ' mm')
print('y-max = ', y, ' mm')
print('z-max = ', z, ' mm')
print('----------------------------------')

V = calcVolume(mask, ds)

print('Volume = ', V, ' sm^3')
print('----------------------------------')


major, minor = majorMinorFromPyradiomics(mask, ds)
print('major Pyradiomics = ', major, ' mm')
print('minor Pyradiomics = ', minor, ' mm')
print('----------------------------------')

R = calcSphereRadius(mask, ds, x, y, z)
print('Sphere radius = ', R, ' mm')

surface = getExternalPoints(mask)
print('coordinates of surface:')
print(surface)
print('Number of surface points = ', len(surface))

coord1, coord2, dist = calcMaxRemotedPoints(surface, ds)

print('Voxel coordinates of the most remote points and distance between them:')
print(coord1, coord2, dist, ' mm')
