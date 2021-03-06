## Process this file with automake to produce Makefile.in

SUBDIRS = centrality clustering community correlations flow generation layout search stats topology util

AM_CPPFLAGS =\
    -I$(srcdir)/.. \
    -I$(srcdir)/../boost-workaround \
    -DHAVE_CONFIG_H

AM_CXXFLAGS =\
    -Wall \
    $(PYTHON_CPPFLAGS) \
    $(BOOST_CPPFLAGS)

AM_CFLAGS=$(AM_CXXFLAGS)

libgraph_tool_coredir = $(pythondir)/graph_tool
libgraph_tool_core_LTLIBRARIES = libgraph_tool_core.la

libgraph_tool_core_la_SOURCES = \
    ../boost-workaround/boost/graph/betweenness_centrality.hpp \
    ../boost-workaround/boost/graph/detail/read_graphviz_new.hpp \
    ../boost-workaround/boost/graph/graphml.hpp \
    ../boost-workaround/boost/graph/graphviz.hpp \
    ../boost-workaround/boost/graph/isomorphism.hpp \
    ../boost-workaround/boost/graph/kamada_kawai_spring_layout.hpp \
    ../boost-workaround/boost/graph/overloading.hpp \
    ../boost-workaround/boost/graph/push_relabel_max_flow.hpp \
    graph.cc \
    graph_bind.cc \
    graph_copy.cc \
    graph_filtering.cc \
    graph_io.cc \
    graph_properties.cc \
    graph_properties_copy.cc \
    graph_properties_group.cc \
    graph_properties_ungroup.cc \
    graph_python_interface.cc \
    graph_python_interface_export.cc \
    graph_selectors.cc \
    graphml.cpp \
    read_graphviz_new.cpp

libgraph_tool_core_la_includedir = $(pythondir)/graph_tool/include
libgraph_tool_core_la_include_HEADERS = \
    ../../config.h \
    fast_vector_property_map.hh \
    gml.hh \
    graph.hh \
    graph_adaptor.hh \
    graph_exceptions.hh \
    graph_filtering.hh \
    graph_properties.hh \
    graph_properties_group.hh \
    graph_python_interface.hh \
    graph_selectors.hh \
    graph_util.hh \
    graph_wrap.hh \
    histogram.hh \
    mpl_nested_loop.hh \
    numpy_bind.hh \
    str_repr.hh \
    shared_map.hh

libgraph_tool_core_la_LIBADD = $(MOD_LIBADD)
libgraph_tool_core_la_LDFLAGS = $(MOD_LDFLAGS)

