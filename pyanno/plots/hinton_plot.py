# Copyright (c) 2011, Enthought, Ltd.
# Author: Pietro Berkes <pberkes@enthought.com>
# License: Apache license

from chaco.data_range_2d import DataRange2D
from chaco.label_axis import LabelAxis
from chaco.scales.scales import FixedScale
from chaco.scales_tick_generator import ScalesTickGenerator
from chaco.api import ArrayPlotData, Plot
from chaco.base import n_gon

from enable.component_editor import ComponentEditor
from traits.has_traits import HasTraits, on_trait_change
from traits.trait_types import Str, ListFloat
from traits.api import Instance
from traitsui.group import VGroup, HGroup
from traitsui.item import Item, Spring
from traitsui.view import View

import numpy as np
from pyanno.plots.plot_tools import SaveToolPlus, CopyDataToClipboardTool


class HintonDiagramPlot(HasTraits):
    """Defines a Hinton diagram view of a discrete probability distribution.

    A Hinton diagram displays a probability distribution as a series of
    squares, with area proportional to the probability mass of each element.

    The plot updates automatically whenever the attribute `data` is modified.
    """

    #### Traits definition ####################################################

    # data to be displayed
    data = ListFloat

    #### plot-related traits
    title = Str

    plot_data = Instance(ArrayPlotData)
    plot = Instance(Plot)

    instructions = Str('Ctrl-S: Save plot,  Ctrl-C: Copy data to clipboard')


    @on_trait_change('data', post_init=True)
    def _update_data(self):
        distr_len = len(self.data)
        plot_data = self.plot_data

        # centers of the squares
        centers = [(i, 0.5) for i in xrange(1, distr_len + 1)]

        for idx, center in enumerate(centers):
            # draw square with area proportional to probability mass
            r = np.sqrt(self.data[idx] / 2.)
            npoints = n_gon(center=center, r=r, nsides=4, rot_degrees=45)
            nxarray, nyarray = np.transpose(npoints)
            # save in dataarray
            plot_data.set_data('x%d' % idx, nxarray)
            plot_data.set_data('y%d' % idx, nyarray)


    def _plot_data_default(self):
        self.plot_data = ArrayPlotData()
        self._update_data()
        return self.plot_data


    #### Plot definition ######################################################

    def _create_probability_axis(self, plot):
        """Create plot axis for probability values."""
        prob_axis = LabelAxis(
            plot,
            orientation='left',
            positions=[0.5, 0.5 + np.sqrt(0.25) / 2., 1.0],
            labels=['0', '0.25', '1']
        )
        prob_axis.tick_generator = ScalesTickGenerator(scale=FixedScale(0.001))
        return prob_axis


    def _create_label_axis(self, len_, plot):
        """Create plot axis for labels at fixed intervals."""
        ids = range(1, len_+1)
        label_list = [str(id-1) for id in ids]
        label_axis = LabelAxis(
            plot,
            orientation='bottom',
            positions=ids,
            labels=label_list,
            label_rotation=0,
            small_haxis_style=True
        )
        # use a FixedScale tick generator with a resolution of 1
        label_axis.tick_generator = ScalesTickGenerator(scale=FixedScale(1.))
        return label_axis


    def _plot_default(self):
        distr_len = len(self.data)

        # PolygonPlot holding the square of the Hinton diagram
        polyplot = Plot(self.plot_data)
        for idx in range(distr_len):
            polyplot.plot(('x%d' % idx, 'y%d' % idx),
                          type="polygon",
                          face_color='black',
                          edge_color='black')

        # remove grids and axes
        polyplot.underlays = []

        # create x axis for labels
        label_axis = self._create_label_axis(distr_len, polyplot)
        polyplot.index_axis = label_axis
        polyplot.underlays.append(label_axis)

        # create y axis for probability density
        #prob_axis = self._create_probability_axis(polyplot)
        #polyplot.value_axis = prob_axis
        #polyplot.underlays.append(prob_axis)

        # tweak some of the plot properties
        #polyplot.padding = 50
        if self.title is not None:
            polyplot.title = self.title
        range2d = DataRange2D(low=(0.5, 0.), high=(distr_len+0.5, 1.))
        polyplot.range2d = range2d
        polyplot.aspect_ratio = ((range2d.x_range.high - range2d.x_range.low)
                                 / (range2d.y_range.high - range2d.y_range.low))

        polyplot.border_visible = False
        polyplot.padding = [15, 15, 15, 25]

        # add tools
        save_tool = SaveToolPlus(component=polyplot)
        copy_tool = CopyDataToClipboardTool(component=polyplot, data=self.data)

        polyplot.tools.append(save_tool)
        polyplot.tools.append(copy_tool)

        return polyplot


    #### View definition ######################################################


    instructions_group = HGroup(
        Spring(),
        Item('instructions', style='readonly', show_label=False),
        Spring()
    )

    resizable_view = View(
        VGroup(
            Item('plot',
                 editor=ComponentEditor(),
                 resizable=True,
                 show_label=False,
                 width = 600,
                 height = 400
            ),
            instructions_group
        ),
        resizable = True
    )

    traits_view = View(
        VGroup(
            Item('plot',
                 editor=ComponentEditor(),
                 resizable=False,
                 show_label=False,
                 height=-100,
            ),
            instructions_group
        )
    )


def plot_hinton_diagram(data, **kwargs):
    """Create and display a Chaco plot of a Hinton diagram.

    The component allows saving the plot (with Ctrl-S), and copying the matrix
    data to the clipboard (with Ctrl-C).

    Keyword arguments:
    title -- title for the resulting plot
    """
    hinton_diagram = HintonDiagramPlot(data=data, **kwargs)
    hinton_diagram.edit_traits(view='resizable_view')
    return hinton_diagram



#### Testing and debugging ####################################################

def main():
    """ Entry point for standalone testing/debugging. """

    data = np.random.random(5)
    data /= data.sum()
    hinton_view = plot_hinton_diagram(data.tolist(),
                                      title='Debug plot_hinton_diagram')
    return hinton_view


if __name__ == '__main__':
    hv = main()