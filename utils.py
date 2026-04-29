# utils.py
import math

def deg2rad(deg):
    """تحويل الدرجات إلى راديان"""
    return deg * math.pi / 180.0

def rad2deg(rad):
    """تحويل الراديان إلى درجات"""
    return rad * 180.0 / math.pi

def safe_divide(a, b):
    """قسمة آمنة (ترجع 0 إذا كان المقام صفراً)"""
    return a / b if b != 0 else 0.0
