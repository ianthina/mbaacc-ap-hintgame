from .Variables import *

from worlds.LauncherComponents import Component, components, launch_subprocess, Type


def launch_client():
    """Launch a client instance"""
    from worlds.mbaacc.Client import launch
    launch_subprocess(launch, name="GameClient")

components.append(Component(
	SHORT_NAME+" Client",
	"GameClient",
	func=launch_client,
	component_type=Type.CLIENT
))