""" Collection of mapping functions from [0,1] to various ranges, used for parameter tuning """

import math as _math

class __MappingFunctions:
    def __init__(self,eps:float=1e-6):
        self.eps = eps

    def setEps(self,eps:float):
        self.eps = eps
    
    @staticmethod
    def scaledMinMax(x:float,min_val:float,max_val:float,func)->float:
        return min_val + (max_val - min_val) * ((func(x)-func(0.0))/(func(1.0)-func(0.0)))
    
    @classmethod
    def exp_01_01(cls,x:float,strength:float=5.0,*,min_val:float=0.0, max_val:float=1.0)->float:
        """ Exponential mapping from [0,1] to [0,1], with f(0)=0+, f(1)=1"""
        assert strength >= 1.0, "strength must be >= 1.0"
        f = lambda z: _math.exp(strength*(z - 1.0))
        return cls.scaledMinMax(x,min_val,max_val,f)
    
    @classmethod
    def exp_01_10(cls,x:float,strength:float=5.0,*,min_val:float=0.0, max_val:float=1.0)->float:
        """ Exponential mapping from [0,1] to [1,0], with f(0)=1-, f(1)=0"""
        return (1-cls.exp_01_01(x, strength=strength, min_val=min_val, max_val=max_val))

    def inv_01_0inf(self,x:float,strength:float=5.0,min_val:float=0.0)->float:
        """ Inverse mapping from [0,1] to [0,inf), with f(0)=0, f(1)->inf"""
        return (strength*x)/(1.0 - x + self.eps) + min_val

    def inv_01_inf0(self,x:float,strength:float=5.0,min_val:float=0.0)->float:
        """ Inverse mapping from [0,1] to [inf,0), with f(0)->inf, f(1)=0"""
        return (1.0 - x)/(strength*x + self.eps) + min_val
    
    @classmethod
    def lin_01_scaled(cls,x:float,min_val:float=0.0,max_val:float=1.0)->float:
        """ Linear mapping from [0,1] to [min_val,max_val]"""
        f = lambda z: z
        return cls.scaledMinMax(x,min_val,max_val,f)
    
    @classmethod
    def neglin_01_scaled(cls,x:float,min_val:float=0.0,max_val:float=1.0)->float:
        """ Negative linear mapping from [0,1] to [max_val,min_val]"""
        return cls.lin_01_scaled(1.0 - x, min_val, max_val)
    
mapping_functions = __MappingFunctions()