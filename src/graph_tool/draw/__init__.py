#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# graph_tool -- a general graph manipulation python module
#
# Copyright (C) 2007-2011 Tiago de Paula Peixoto <tiago@skewed.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
``graph_tool.draw`` - Graph drawing
-----------------------------------

Summary
+++++++

.. autosummary::
   :nosignatures:

   graph_draw
   fruchterman_reingold_layout
   arf_layout
   random_layout

Contents
++++++++
"""

import sys
import os
import os.path
import time
import warnings
import ctypes
import ctypes.util
import tempfile
from .. import _degree, _prop, PropertyMap, _check_prop_vector,\
     _check_prop_scalar, _check_prop_writable, group_vector_property,\
     ungroup_vector_property, GraphView
from .. topology import label_components
from .. decorators import _limit_args
import numpy.random
from numpy import *
import copy

from .. dl_import import dl_import
dl_import("import libgraph_tool_layout")

try:
    import matplotlib.cm
    import matplotlib.colors
except ImportError:
    warnings.warn("error importing matplotlib module... " + \
                  "graph_draw() will not work.", ImportWarning)

try:
    libname = ctypes.util.find_library("c")
    libc = ctypes.CDLL(libname)
    if hasattr(libc, "open_memstream"):
        libc.open_memstream.restype = ctypes.POINTER(ctypes.c_char)
except OSError:
    pass

try:
    libname = ctypes.util.find_library("gvc")
    if libname is None:
        raise OSError()
    libgv = ctypes.CDLL(libname)
    # properly set the return types of certain functions
    ptype = ctypes.POINTER(ctypes.c_char)
    libgv.gvContext.restype = ptype
    libgv.agopen.restype = ptype
    libgv.agnode.restype = ptype
    libgv.agedge.restype = ptype
    libgv.agget.restype = ptype
    libgv.agstrdup_html.restype = ptype
    # create a context to use the whole time (if we keep freeing and recreating
    # it, we will hit a memory leak in graphviz)
    gvc = libgv.gvContext()
except OSError:
    warnings.warn("error importing graphviz C library (libgvc)... " + \
                  "graph_draw() will not work.", ImportWarning)


__all__ = ["graph_draw", "fruchterman_reingold_layout", "arf_layout",
           "random_layout"]


def htmlize(val):
    if len(val) >= 2 and val[0] == "<" and val[-1] == ">":
        return ctypes.string_at(libgv.agstrdup_html(val[1:-1]))
    return val


def aset(elem, attr, value):
    v = htmlize(str(value))
    libgv.agsafeset(elem, str(attr), v, v)


def aget(elem, attr):
    return ctypes.string_at(libgv.agget(elem, str(attr)))


def graph_draw(g, pos=None, size=(15, 15), pin=False, layout=None, maxiter=None,
               ratio="fill", overlap=True, sep=None, splines=False,
               vsize=0.105, penwidth=1.0, elen=None, gprops={}, vprops={},
               eprops={}, vcolor="#a40000", ecolor="#2e3436", vcmap=None,
               vnorm=True, ecmap=None, enorm=True, vorder=None, eorder=None,
               output="", output_format="auto", fork=False,
               return_string=False):
    r"""Draw a graph using graphviz.

    Parameters
    ----------
    g : :class:`~graph_tool.Graph`
        Graph to be drawn.
    pos : :class:`~graph_tool.PropertyMap` or tuple of :class:`~graph_tool.PropertyMap` (optional, default: ``None``)
        Vertex property maps containing the x and y coordinates of the vertices.
    size : tuple of scalars (optional, default: ``(15,15)``)
        Size (in centimeters) of the canvas.
    pin : bool or :class:`~graph_tool.PropertyMap` (default: ``False``)
        If ``True``, the vertices are not moved from their initial position. If
        a :class:`~graph_tool.PropertyMap` is passed, it is used to pin nodes
        individually.
    layout : string (default: ``"neato" if g.num_vertices() <= 1000 else "sfdp"``)
        Layout engine to be used. Possible values are ``"neato"``, ``"fdp"``,
        ``"dot"``, ``"circo"``, ``"twopi"`` and ``"arf"``.
    maxiter : int (default: ``None``)
        If specified, limits the maximum number of iterations.
    ratio : string or float (default: ``"fill"``)
        Sets the aspect ratio (drawing height/drawing width) for the
        drawing. Note that this is adjusted before the ``size`` attribute
        constraints are enforced.

        If ``ratio`` is numeric, it is taken as the desired aspect ratio. Then,
        if the actual aspect ratio is less than the desired ratio, the drawing
        height is scaled up to achieve the desired ratio; if the actual ratio is
        greater than that desired ratio, the drawing width is scaled up.

        If ``ratio == "fill"`` and the size attribute is set, node positions are
        scaled, separately in both x and y, so that the final drawing exactly
        fills the specified size.

        If ``ratio == "compress"`` and the size attribute is set, dot attempts
        to compress the initial layout to fit in the given size. This achieves a
        tighter packing of nodes but reduces the balance and symmetry.  This
        feature only works in dot.

        If ``ratio == "expand"``, the size attribute is set, and both the width
        and the height of the graph are less than the value in size, node
        positions are scaled uniformly until at least one dimension fits size
        exactly.  Note that this is distinct from using size as the desired
        size, as here the drawing is expanded before edges are generated and all
        node and text sizes remain unchanged.

        If ``ratio == "auto"``, the page attribute is set and the graph cannot
        be drawn on a single page, then size is set to an "ideal" value. In
        particular, the size in a given dimension will be the smallest integral
        multiple of the page size in that dimension which is at least half the
        current size. The two dimensions are then scaled independently to the
        new size. This feature only works in dot.
    overlap : bool or string (default: ``"prism"``)
        Determines if and how node overlaps should be removed. Nodes are first
        enlarged using the sep attribute. If ``True``, overlaps are retained. If
        the value is ``"scale"``, overlaps are removed by uniformly scaling in x
        and y. If the value is ``False``, node overlaps are removed by a
        Voronoi-based technique. If the value is ``"scalexy"``, x and y are
        separately scaled to remove overlaps.

        If sfdp is available, one can set overlap to ``"prism"`` to use a
        proximity graph-based algorithm for overlap removal. This is the
        preferred technique, though ``"scale"`` and ``False`` can work well with
        small graphs. This technique starts with a small scaling up, controlled
        by the overlap_scaling attribute, which can remove a significant portion
        of the overlap. The prism option also accepts an optional non-negative
        integer suffix. This can be used to control the number of attempts made
        at overlap removal. By default, ``overlap == "prism"`` is equivalent to
        ``overlap == "prism1000"``. Setting ``overlap == "prism0"`` causes only
        the scaling phase to be run.

        If the value is ``"compress"``, the layout will be scaled down as much
        as possible without introducing any overlaps, obviously assuming there
        are none to begin with.
    sep : float (default: ``None``)
        Specifies margin to leave around nodes when removing node overlap. This
        guarantees a minimal non-zero distance between nodes.
    splines : bool (default: ``False``)
        If ``True``, the edges are drawn as splines and routed around the
        vertices.
    vsize : float, :class:`~graph_tool.PropertyMap`, or tuple (default: ``0.105``)
        Default vertex size (width and height). If a tuple is specified, the
        first value should be a property map, and the second is a scale factor.
    penwidth : float, :class:`~graph_tool.PropertyMap` or tuple (default: ``1.0``)
        Specifies the width of the pen, in points, used to draw lines and
        curves, including the boundaries of edges and clusters. It has no effect
        on text. If a tuple is specified, the first value should be a property
        map, and the second is a scale factor.
    elen : float or :class:`~graph_tool.PropertyMap` (default: ``None``)
        Preferred edge length, in inches.
    gprops : dict (default: ``{}``)
        Additional graph properties, as a dictionary. The keys are the property
        names, and the values must be convertible to string.
    vprops : dict (default: ``{}``)
        Additional vertex properties, as a dictionary. The keys are the property
        names, and the values must be convertible to string, or vertex property
        maps, with values convertible to strings.
    eprops : dict (default: ``{}``)
        Additional edge properties, as a dictionary. The keys are the property
        names, and the values must be convertible to string, or edge property
        maps, with values convertible to strings.
    vcolor : string or :class:`~graph_tool.PropertyMap` (default: ``"#a40000"``)
        Drawing color for vertices. If the valued supplied is a property map,
        the values must be scalar types, whose color values are obtained from
        the ``vcmap`` argument.
    ecolor : string or :class:`~graph_tool.PropertyMap` (default: ``"#2e3436"``)
        Drawing color for edges. If the valued supplied is a property map,
        the values must be scalar types, whose color values are obtained from
        the ``ecmap`` argument.
    vcmap : :class:`matplotlib.colors.Colormap` (default: :class:`matplotlib.cm.jet`)
        Vertex color map.
    vnorm : bool (default: ``True``)
        Normalize vertex color values to the [0,1] range.
    ecmap : :class:`matplotlib.colors.Colormap` (default: :class:`matplotlib.cm.jet`)
        Edge color map.
    enorm : bool (default: ``True``)
        Normalize edge color values to the [0,1] range.
    vorder : :class:`~graph_tool.PropertyMap` (default: ``None``)
        Scalar vertex property map which specifies the order with which vertices
        are drawn.
    eorder : :class:`~graph_tool.PropertyMap` (default: ``None``)
        Scalar edge property map which specifies the order with which edges
        are drawn.
    output : string (default: ``""``)
        Output file name.
    output_format : string (default: ``"auto"``)
        Output file format. Possible values are ``"auto"``, ``"xlib"``,
        ``"ps"``, ``"svg"``, ``"svgz"``, ``"fig"``, ``"mif"``, ``"hpgl"``,
        ``"pcl"``, ``"png"``, ``"gif"``, ``"dia"``, ``"imap"``, ``"cmapx"``. If
        the value is ``"auto"``, the format is guessed from the ``output``
        parameter, or ``xlib`` if it is empty. If the value is ``None``, no
        output is produced.
    fork : bool (default: ``False``)
        If ``True``, the program is forked before drawing. This is used as a
        work-around for a bug in graphviz, where the ``exit()`` function is
        called, which would cause the calling program to end. This is always
        assumed ``True``, if ``output_format == 'xlib'``.
    return_string : bool (default: ``False``)
        If ``True``, a string containing the rendered graph as binary data is
        returned (defaults to png format).

    Returns
    -------
    pos : :class:`~graph_tool.PropertyMap`
        Vector vertex property map with the x and y coordinates of the vertices.
    gv : gv.digraph or gv.graph (optional, only if ``returngv == True``)
        Internally used graphviz graph.


    Notes
    -----
    This function is a wrapper for the [graphviz] routines. Extensive additional
    documentation for the graph, vertex and edge properties is available at:
    http://www.graphviz.org/doc/info/attrs.html.


    Examples
    --------
    >>> from numpy import *
    >>> from numpy.random import seed, zipf
    >>> seed(42)
    >>> g = gt.random_graph(1000, lambda: min(zipf(2.4), 40),
    ...                     lambda i, j: exp(abs(i - j)), directed=False)
    >>> # extract largest component
    >>> g = gt.GraphView(g, vfilt=gt.label_largest_component(g))
    >>> deg = g.degree_property_map("out")
    >>> deg.a = 2 * (sqrt(deg.a) * 0.5 + 0.4)
    >>> ebet = gt.betweenness(g)[1]
    >>> ebet.a *= 4000
    >>> ebet.a += 10
    >>> gt.graph_draw(g, vsize=deg, vcolor=deg, vorder=deg, elen=10,
    ...               ecolor=ebet, eorder=ebet, penwidth=ebet,
    ...               overlap="prism", output="graph-draw.pdf")
    <...>

    .. figure:: graph-draw.*
        :align: center

        Kamada-Kawai force-directed layout of a graph with a power-law degree
        distribution, and dissortative degree correlation. The vertex size and
        color indicate the degree, and the edge color and width the edge
        betweeness centrality.

    References
    ----------
    .. [graphviz] http://www.graphviz.org

    """

    if output != "" and output is not None:
        output = os.path.expanduser(output)
        # check opening file for writing, since graphviz will bork if it is not
        # possible to open file
        if os.path.dirname(output) != "" and \
               not os.access(os.path.dirname(output), os.W_OK):
            raise IOError("cannot write to " + os.path.dirname(output))

    has_layout = False
    try:
        gvg = libgv.agopen("G", 1 if g.is_directed() else 0)

        if layout is None:
            if pin == False:
                layout = "neato" if g.num_vertices() <= 1000 else "sfdp"
            else:
                layout = "neato"

        if layout == "arf":
            layout = "neato"
            pos = arf_layout(g, pos=pos)
            pin = True

        if pos is not None:
            # copy user-supplied property
            if isinstance(pos, PropertyMap):
                pos = ungroup_vector_property(pos, [0, 1])
            else:
                pos = (g.copy_property(pos[0]), g.copy_property(pos[1]))

        if type(vsize) == tuple:
            s = g.new_vertex_property("double")
            g.copy_property(vsize[0], s)
            s.a *= vsize[1]
            vsize = s

        if type(penwidth) == tuple:
            s = g.new_edge_property("double")
            g.copy_property(penwidth[0], s)
            s.a *= penwidth[1]
            penwidth = s

        # main graph properties
        aset(gvg, "outputorder", "edgesfirst")
        aset(gvg, "mode", "major")
        if type(overlap) is bool:
            overlap = "true" if overlap else "false"
        else:
            overlap = str(overlap)
        aset(gvg, "overlap", overlap)
        if sep is not None:
            aset(gvg, "sep", sep)
        if splines:
            aset(gvg, "splines", "true")
        aset(gvg, "ratio", ratio)
        # size is in centimeters... convert to inches
        aset(gvg, "size", "%f,%f" % (size[0] / 2.54, size[1] / 2.54))
        if maxiter is not None:
            aset(gvg, "maxiter", maxiter)

        seed = numpy.random.randint(sys.maxint)
        aset(gvg, "start", "%d" % seed)

        # apply all user supplied graph properties
        for k, val in gprops.iteritems():
            if isinstance(val, PropertyMap):
                aset(gvg, k, val[g])
            else:
                aset(gvg, k, val)

        # normalize color properties
        if (isinstance(vcolor, PropertyMap) and
            vcolor.value_type() != "string"):
            minmax = [float("inf"), -float("inf")]
            for v in g.vertices():
                c = vcolor[v]
                minmax[0] = min(c, minmax[0])
                minmax[1] = max(c, minmax[1])
            if minmax[0] == minmax[1]:
                minmax[1] += 1
            if vnorm:
                vnorm = matplotlib.colors.normalize(vmin=minmax[0], vmax=minmax[1])
            else:
                vnorm = lambda x: x

        if (isinstance(ecolor, PropertyMap) and
            ecolor.value_type() != "string"):
            minmax = [float("inf"), -float("inf")]
            for e in g.edges():
                c = ecolor[e]
                minmax[0] = min(c, minmax[0])
                minmax[1] = max(c, minmax[1])
            if minmax[0] == minmax[1]:
                minmax[1] += 1
            if enorm:
                enorm = matplotlib.colors.normalize(vmin=minmax[0],
                                                    vmax=minmax[1])
            else:
                enorm = lambda x: x

        if vcmap is None:
            vcmap = matplotlib.cm.jet

        if ecmap is None:
            ecmap = matplotlib.cm.jet

        # add nodes
        if vorder is not None:
            vertices = sorted(g.vertices(), lambda a, b: cmp(vorder[a], vorder[b]))
        else:
            vertices = g.vertices()
        for v in vertices:
            n = libgv.agnode(gvg, str(int(v)))

            if type(vsize) == PropertyMap:
                vw = vh = vsize[v]
            else:
                vw = vh = vsize

            aset(n, "shape", "circle")
            aset(n, "width", "%g" % vw)
            aset(n, "height", "%g" % vh)
            aset(n, "style", "filled")
            aset(n, "color", "#2e3436")
            # apply color
            if isinstance(vcolor, str):
                aset(n, "fillcolor", vcolor)
            else:
                color = vcolor[v]
                if isinstance(color, str):
                    aset(n, "fillcolor", color)
                else:
                    color = tuple([int(c * 255.0) for c in vcmap(vnorm(color))])
                    aset(n, "fillcolor", "#%.2x%.2x%.2x%.2x" % color)
            aset(n, "label", "")

            # user supplied position
            if pos is not None:
                if isinstance(pin, bool):
                    pin_val = pin
                else:
                    pin_val = pin[v]
                aset(n, "pos", "%f,%f%s" % (pos[0][v], pos[1][v],
                                            "!" if pin_val else ""))
                aset(n, "pin", pin_val)

            # apply all user supplied properties
            for k, val in vprops.iteritems():
                if isinstance(val, PropertyMap):
                    aset(n, k, val[v])
                else:
                    aset(n, k, val)

        # add edges
        if eorder is not None:
            edges = sorted(g.edges(), lambda a, b: cmp(eorder[a], eorder[b]))
        else:
            edges = g.edges()
        for e in edges:
            ge = libgv.agedge(gvg,
                              libgv.agnode(gvg, str(int(e.source()))),
                              libgv.agnode(gvg, str(int(e.target()))))
            aset(ge, "arrowsize", "0.3")
            if g.is_directed():
                aset(ge, "arrowhead", "vee")

            # apply color
            if isinstance(ecolor, str):
                aset(ge, "color", ecolor)
            else:
                color = ecolor[e]
                if isinstance(color, str):
                    aset(ge, "color", color)
                else:
                    color = tuple([int(c * 255.0) for c in ecmap(enorm(color))])
                    aset(ge, "color", "#%.2x%.2x%.2x%.2x" % color)

            # apply edge length
            if elen is not None:
                if isinstance(elen, PropertyMap):
                    aset(ge, "len", elen[e])
                else:
                    aset(ge, "len", elen)

            # apply width
            if penwidth is not None:
                if isinstance(penwidth, PropertyMap):
                    aset(ge, "penwidth", penwidth[e])
                else:
                    aset(ge, "penwidth", penwidth)

            # apply all user supplied properties
            for k, v in eprops.iteritems():
                if isinstance(v, PropertyMap):
                    aset(ge, k, v[e])
                else:
                    aset(ge, k, v)

        libgv.gvLayout(gvc, gvg, layout)
        has_layout = True
        retv = libgv.gvRender(gvc, gvg, "dot", None)  # retrieve positions only

        if pos == None:
            pos = (g.new_vertex_property("double"),
                   g.new_vertex_property("double"))
        for v in g.vertices():
            n = libgv.agnode(gvg, str(int(v)))
            p = aget(n, "pos")
            p = p.split(",")
            pos[0][v] = float(p[0])
            pos[1][v] = float(p[1])

        # I don't get this, but it seems necessary
        pos[0].a /= 100
        pos[1].a /= 100

        pos = group_vector_property(pos)

        if return_string:
            if output_format == "auto":
                output_format = "png"
            if hasattr(libc, "open_memstream"):
                buf = ctypes.c_char_p()
                buf_len = ctypes.c_size_t()
                fstream = libc.open_memstream(ctypes.byref(buf),
                                              ctypes.byref(buf_len))
                libgv.gvRender(gvc, gvg, output_format, fstream)
                libc.fclose(fstream)
                data = copy.copy(ctypes.string_at(buf, buf_len.value))
                libc.free(buf)
            else:
                # write to temporary file, if open_memstream is not available
                output = tempfile.mkstemp()[1]
                libgv.gvRenderFilename(gvc, gvg, output_format, output)
                data = open(output).read()
                os.remove(output)
        else:
            if output_format == "auto":
                if output == "":
                    output_format = "xlib"
                elif output is not None:
                    output_format = output.split(".")[-1]

            # if using xlib we need to fork the process, otherwise good ol'
            # graphviz will call exit() when the window is closed
            if output_format == "xlib" or fork:
                pid = os.fork()
                if pid == 0:
                    libgv.gvRenderFilename(gvc, gvg, output_format, output)
                    os._exit(0)  # since we forked, it's good to be sure
                if output_format != "xlib":
                    os.wait()
            elif output is not None:
                libgv.gvRenderFilename(gvc, gvg, output_format, output)

        ret = [pos]
        if return_string:
            ret.append(data)

    finally:
        if has_layout:
            libgv.gvFreeLayout(gvc, gvg)
        libgv.agclose(gvg)

    if len(ret) > 1:
        return tuple(ret)
    else:
        return ret[0]


def random_layout(g, shape=None, pos=None, dim=2):
    r"""Performs a random layout of the graph.

    Parameters
    ----------
    g : :class:`~graph_tool.Graph`
        Graph to be used.
    shape : tuple or list (optional, default: ``None``)
        Rectangular shape of the bounding area. The size of this parameter must
        match `dim`, and each element can be either a pair specifying a range,
        or a single value specifying a range starting from zero. If None is
        passed, a square of linear size :math:`\sqrt{N}` is used.
    pos : :class:`~graph_tool.PropertyMap` (optional, default: ``None``)
        Vector vertex property maps where the coordinates should be stored.
    dim : int (optional, default: ``2``)
        Number of coordinates per vertex.

    Returns
    -------
    pos : :class:`~graph_tool.PropertyMap`
        A vector-valued vertex property map with the coordinates of the
        vertices.

    Notes
    -----
    This algorithm has complexity :math:`O(V)`.

    Examples
    --------
    >>> from numpy.random import seed
    >>> seed(42)
    >>> g = gt.random_graph(100, lambda: (3, 3))
    >>> shape = [[50, 100], [1, 2], 4]
    >>> pos = gt.random_layout(g, shape=shape, dim=3)
    >>> pos[g.vertex(0)].a
    array([ 86.59969709,   1.31435598,   0.64651486])

    """

    if pos == None:
        pos = g.new_vertex_property("vector<double>")
    _check_prop_vector(pos, name="pos")

    pos = ungroup_vector_property(pos, range(0, dim))

    if shape == None:
        shape = [sqrt(g.num_vertices())] * dim

    for i in xrange(dim):
        if hasattr(shape[i], "__len__"):
            if len(shape[i]) != 2:
                raise ValueError("The elements of 'shape' must have size 2.")
            r = [min(shape[i]), max(shape[i])]
        else:
            r = [min(shape[i], 0), max(shape[i], 0)]
        d = r[1] - r[0]

        # deal with filtering
        p = pos[i].ma
        p[:] = numpy.random.random(len(p)) * d + r[0]

    pos = group_vector_property(pos)
    return pos


def fruchterman_reingold_layout(g, weight=None, a=None, r=1., scale=None,
                                circular=False, grid=True, t_range=None,
                                n_iter=100, pos=None):
    r"""Calculate the Fruchterman-Reingold spring-block layout of the graph.

    Parameters
    ----------
    g : :class:`~graph_tool.Graph`
        Graph to be used.
    weight : :class:`PropertyMap` (optional, default: ``None``)
        An edge property map with the respective weights.
    a : float (optional, default: :math:`V`)
        Attracting force between adjacent vertices.
    r : float (optional, default: 1.0)
        Repulsive force between vertices.
    scale : float (optional, default: :math:`\sqrt{V}`)
        Total scale of the layout (either square side or radius).
    circular : bool (optional, default: ``False``)
        If ``True``, the layout will have a circular shape. Otherwise the shape
        will be a square.
    grid : bool (optional, default: ``True``)
        If ``True``, the repulsive forces will only act on vertices which are on
        the same site on a grid. Otherwise they will act on all vertex pairs.
    t_range : tuple of floats (optional, default: ``(scale / 10, scale / 1000)``)
        Temperature range used in annealing. The temperature limits the
        displacement at each iteration.
    n_iter : int (optional, default: ``100``)
        Total number of iterations.
    pos : :class:`PropertyMap` (optional, default: ``None``)
        Vector vertex property maps where the coordinates should be stored. If
        provided, this will also be used as the initial position of the
        vertices.

    Returns
    -------
    pos : :class:`~graph_tool.PropertyMap`
        A vector-valued vertex property map with the coordinates of the
        vertices.

    Notes
    -----
    This algorithm is defined in [fruchterman-reingold]_, and has
    complexity :math:`O(\text{n-iter}\times V^2)` if `grid=False` or
    :math:`O(\text{n-iter}\times (V + E))` otherwise.

    Examples
    --------
    >>> from numpy.random import seed, zipf
    >>> seed(42)
    >>> g = gt.price_network(300)
    >>> pos = gt.fruchterman_reingold_layout(g, n_iter=1000)
    >>> gt.graph_draw(g, pos=pos, pin=True, output="graph-draw-fr.pdf")
    <...>

    .. figure:: graph-draw-fr.*
        :align: center

        Fruchterman-Reingold layout of a Price network.

    References
    ----------
    .. [fruchterman-reingold] Fruchterman, Thomas M. J.; Reingold, Edward M.
       "Graph Drawing by Force-Directed Placement". Software – Practice & Experience
       (Wiley) 21 (11): 1129–1164. (1991) :doi:`10.1002/spe.4380211102`
    """

    if pos == None:
        pos = random_layout(g, dim=2)
    _check_prop_vector(pos, name="pos", floating=True)

    if a is None:
        a = float(g.num_vertices())

    if scale is None:
        scale = sqrt(g.num_vertices())

    if t_range is None:
        t_range = (scale / 10, scale / 1000)

    ug = GraphView(g, directed=False)
    libgraph_tool_layout.fruchterman_reingold_layout(ug._Graph__graph,
                                                     _prop("v", g, pos),
                                                     _prop("e", g, weight),
                                                     a, r, not circular, scale,
                                                     grid, t_range[0],
                                                     t_range[1], n_iter)
    return pos


def arf_layout(g, weight=None, d=0.5, a=10, dt=0.001, epsilon=1e-6,
               max_iter=1000, pos=None, dim=2):
    r"""Calculate the ARF spring-block layout of the graph.

    Parameters
    ----------
    g : :class:`~graph_tool.Graph`
        Graph to be used.
    weight : :class:`~graph_tool.PropertyMap` (optional, default: ``None``)
        An edge property map with the respective weights.
    d : float (optional, default: ``0.5``)
        Opposing force between vertices.
    a : float (optional, default: ``10``)
        Attracting force between adjacent vertices.
    dt : float (optional, default: ``0.001``)
        Iteration step size.
    epsilon : float (optional, default: ``1e-6``)
        Convergence criterion.
    max_iter : int (optional, default: ``1000``)
        Maximum number of iterations. If this value is ``0``, it runs until
        convergence.
    pos : :class:`~graph_tool.PropertyMap` (optional, default: ``None``)
        Vector vertex property maps where the coordinates should be stored.
    dim : int (optional, default: ``2``)
        Number of coordinates per vertex.

    Returns
    -------
    pos : :class:`~graph_tool.PropertyMap`
        A vector-valued vertex property map with the coordinates of the
        vertices.

    Notes
    -----
    This algorithm is defined in [geipel-self-organization-2007]_, and has
    complexity :math:`O(V^2)`.

    Examples
    --------
    >>> from numpy.random import seed, zipf
    >>> seed(42)
    >>> g = gt.price_network(300)
    >>> pos = gt.arf_layout(g, max_iter=0)
    >>> gt.graph_draw(g, pos=pos, pin=True, output="graph-draw-arf.pdf")
    <...>

    .. figure:: graph-draw-arf.*
        :align: center

        ARF layout of a Price network.

    References
    ----------
    .. [geipel-self-organization-2007] Markus M. Geipel, "Self-Organization
       applied to Dynamic Network Layout", International Journal of Modern
       Physics C vol. 18, no. 10 (2007), pp. 1537-1549,
       :doi:`10.1142/S0129183107011558`, :arxiv:`0704.1748v5`
    .. _arf: http://www.sg.ethz.ch/research/graphlayout
    """

    if pos is None:
        if dim != 2:
            pos = random_layout(g, dim=dim)
        else:
            pos = graph_draw(g, output=None)
    _check_prop_vector(pos, name="pos", floating=True)

    ug = GraphView(g, directed=False)
    libgraph_tool_layout.arf_layout(ug._Graph__graph, _prop("v", g, pos),
                                    _prop("e", g, weight), d, a, dt, max_iter,
                                    epsilon, dim)
    return pos
