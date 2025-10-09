"""This is a somewhat delicate package. It contains all registered components
and preconfigured templates.

Hence, it imports all of the components. To avoid cycles, no component should
import this in module scope."""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import typing
from base import utils
from typing import Any
from typing import Optional
from typing import Text
from typing import Type


def get_component_class(component_name):
    try:
        return utils.class_from_module_path(component_name)
    except Exception:
        raise Exception(
                "Failed to find component class for '{}'. Unknown "
                "component name. Check your configured pipeline and make "
                "sure the mentioned component is not misspelled. If you "
                "are creating your own component, make sure it is either "
                "listed as part of the `component_classes` in "
                "`rasa_nlu.registry.py` or is a proper name of a class "
                "in a module.".format(component_name))


def create_component_by_name(component_name):
    # type: (Text, RasaNLUModelConfig) -> Optional[Component]
    """Resolves a component and calls it's create method to init it based on a
    previously persisted model."""

    component_clz = get_component_class(component_name)
    return component_clz.create()
