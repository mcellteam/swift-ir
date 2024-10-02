import numpy as np
import cvxpy as cp


def ion(p0, p1, p):

    return (-p0[1] * p1[0] + p0[0] * p1[1] + p0[1] * p[0]
            - p1[1] * p[0] - p0[0] * p[1] + p1[0] * p[1])


def maair(arg):

    ax = cp.Variable()
    ay = cp.Variable()
    bx = cp.Variable()
    dy = cp.Variable()
    vs = [(ax, ay), (bx, ay), (bx, dy), (ax, dy)]
    obj = cp.Maximize(cp.log(bx - ax) + cp.log(dy - ay))
    cons = []

    if ion(*arg[:3]) > 0:    # ccw
        pol = arg
    else:
        pol = arg[::-1]    # make it ccw
    for i in range(len(arg)):
        for v in vs:
            cons.append(ion(pol[i], pol[(i + 1) % len(arg)], v) >= 0)

    prob = cp.Problem(obj, cons)
    prob.solve()

    rec = np.array([[ax.value, ay.value], [bx.value, ay.value],
                    [bx.value, dy.value], [ax.value, dy.value]])

    return prob.status, prob.value, cp.exp(prob.value).value.item(), rec