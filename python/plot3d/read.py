import numpy as np 
import os.path as osp
import struct
from typing import List
from .block import Block
from scipy.io import FortranFile

def __read_plot3D_chunk_binary(f,IMAX:int,JMAX:int,KMAX:int, big_endian:bool=False):
    """Reads and formats a binary chunk of data into a plot3D block

    Args:
        f (io): file handle
        IMAX (int): maximum I index
        JMAX (int): maximum J index
        KMAX (int): maximum K index
        big_endian (bool, Optional): Use big endian format for reading binary files. Defaults False.

    Returns:
        numpy.ndarray: Plot3D variable either X,Y, or Z 
    """
    A = np.empty(shape=(IMAX, JMAX, KMAX))
    for k in range(KMAX):
        for j in range(JMAX):
            for i in range(IMAX):
                A[i,j,k] = struct.unpack(">f",f.read(4))[0] if big_endian else struct.unpack("f",f.read(4))[0]
    return A

def __read_plot3D_chunk_ASCII(tokenArray:List[str],offset:int,IMAX:int,JMAX:int,KMAX:int):
    """Reads an ascii chunk of plot3D data into a block 

    Args:
        tokenArray (List[str]): this is a list of strings separated by a space, new line character removed ["12","22", ... etc]
        offset (int): how many entries to skip in the array based on block size (IMAX*JMAX*KMAX) of the previous block
        IMAX (int): maximum I index
        JMAX (int): maximum J index
        KMAX (int): maximum K index 

    Returns:
        numpy.ndarray: Plot3D variable either X,Y, or Z
    """
    '''Works for ASCII files 
    '''
    A = np.empty(shape=(IMAX, JMAX, KMAX))
    for k in range(KMAX):
        for j in range(JMAX):
            for i in range(IMAX):
                A[i,j,k] = tokenArray[offset]
                offset+=1

    return A, offset

def read_ap_nasa(filename:str):
    """Reads an AP NASA File and converts it to Block format which can be exported to a plot3d file
        AP NASA file represents a single block. The first 7 integers are il,jl,kl,ile,ite,jtip,nbld
    
    Args:
        filename (str): location of the .ap file

    Returns:
        Tuple containing: 

            *block* (Block): file in block format
            *nbld* (int): Number of blades 
    """

    f = FortranFile(filename, 'r')

    ints = f.read_ints(np.int32)
    idim = np.array([ints[0],ints[1],ints[2]])
    mdim = np.array([3,ints[0]*ints[2]])
    il = ints[0]
    jl = ints[1]
    kl = ints[2]
    jdim = jl 

    ile = ints[3]
    ite = ints[4]
    jtip = ints[5]
    nbld = ints[6]

    for j in range(0,jdim):
        jmeshxrt = f.read_reals(dtype='f4').reshape(mdim)
        meshi    = np.array(jmeshxrt[0,:])
        meshj    = np.array(jmeshxrt[1,:])
        meshk    = np.array(jmeshxrt[2,:])
        if j == 0:
            meshx   = meshi
            meshr   = meshj
            mesht   = meshk
        else:
            meshx = np.append(meshx,meshi)
            meshr = np.append(meshr,meshj)
            mesht = np.append(mesht,meshk)

    meshx = meshx.reshape(ints[1],ints[2],ints[0])
    meshr = meshr.reshape(ints[1],ints[2],ints[0])
    mesht = mesht.reshape(ints[1],ints[2],ints[0])

    # Convert from x,r,theta to x,y,z
    z = meshr*np.sin(mesht)
    y = meshr*np.cos(mesht)

    return Block(X=meshx,Y=y,Z=z), nbld


def read_plot3D(filename:str, binary:bool=True,big_endian:bool=False):
    """Reads a plot3d file and returns Blocks

    Args:
        filename (str): name of the file to read, .p3d, .xyz, .pdc, .plot3d? 
        binary (bool, optional): indicates if the file is binary. Defaults to True.
        big_endian (bool, optional): use big endian format for reading binary files

    Returns:
        List[Block]: List of blocks insdie the plot3d file
    """
    
    blocks = list()
    if osp.isfile(filename):
        if binary:
            with open(filename,'rb') as f:
                nblocks = struct.unpack(">I",f.read(4))[0] if big_endian else struct.unpack("I",f.read(4))[0] # Read bytes            
                IMAX = list(); JMAX = list(); KMAX = list()
                for b in range(nblocks):
                    if big_endian:
                        IMAX.append(struct.unpack(">I",f.read(4))[0]) # Read bytes
                        JMAX.append(struct.unpack(">I",f.read(4))[0]) # Read bytes
                        KMAX.append(struct.unpack(">I",f.read(4))[0]) # Read bytes
                    else:
                        IMAX.append(struct.unpack("I",f.read(4))[0]) # Read bytes
                        JMAX.append(struct.unpack("I",f.read(4))[0]) # Read bytes
                        KMAX.append(struct.unpack("I",f.read(4))[0]) # Read bytes

                for b in range(nblocks):
                    X = __read_plot3D_chunk_binary(f,IMAX[b],JMAX[b],KMAX[b], big_endian)
                    Y = __read_plot3D_chunk_binary(f,IMAX[b],JMAX[b],KMAX[b], big_endian)
                    Z = __read_plot3D_chunk_binary(f,IMAX[b],JMAX[b],KMAX[b], big_endian)
                    b_temp = Block(X,Y,Z)                    
                    blocks.append(b_temp)
        else:
            with open(filename,'r') as f: 
                nblocks = int(f.readline())
                IMAX = list(); JMAX = list(); KMAX = list()
                
                for b in range(nblocks):
                    IJK = f.readline().replace('\n','').split(' ')
                    tokens = [int(w) for w in IJK if w]
                    IMAX.append(tokens[0])
                    JMAX.append(tokens[1])
                    KMAX.append(tokens[2])
                
                lines = [l.replace('\n','').split(' ') for l in f.readlines()] # Basically an array of strings representing numbers
                lines = [item for sublist in lines for item in sublist]         # Flatten list of lists https://stackabuse.com/python-how-to-flatten-list-of-lists/
 
                tokenArray = [float(entry) for entry in lines if entry] # Convert everything to float 
                offset = 0
                for b in range(nblocks):
                    X, offset = __read_plot3D_chunk_ASCII(tokenArray,offset,IMAX[b],JMAX[b],KMAX[b])
                    Y, offset = __read_plot3D_chunk_ASCII(tokenArray,offset,IMAX[b],JMAX[b],KMAX[b])
                    Z, offset = __read_plot3D_chunk_ASCII(tokenArray,offset,IMAX[b],JMAX[b],KMAX[b])
                    b_temp = Block(X,Y,Z)                    
                    blocks.append(b_temp)
    return blocks


