import numpy


def mapCalc(angleOne, pwmOne, angleTwo, pwmTwo):
    angleOne = 180 - angleOne
    if angleOne < 0:
        angleOne = angleOne + 360

    angleTwo = 180 - angleTwo
    if angleTwo < 0:
        angleTwo = angleTwo + 360

    angleOne = angleOne * 4
    angleTwo = angleTwo * 4

    a = numpy.array([[angleOne, 4], [angleTwo, 4]])
    b = numpy.array([pwmOne, pwmTwo])
    x = numpy.linalg.solve(a, b)

    print x


# input values in the order degreesOne, pwmOne, degreesTwo, pwmTwo
mapCalc(90, 4350, 270, 7050)
