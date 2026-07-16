from calibre.customize import InterfaceActionBase


class CalibreKnowledgePlugin(InterfaceActionBase):
    """Calibre interface-action entry point."""

    name = 'Library Mentor'
    description = 'Ask questions of your books and get a short daily learning plan.'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Local Library Tools'
    version = (1, 0, 0)
    minimum_calibre_version = (6, 0, 0)
    # Calibre exposes the root of a plugin ZIP as calibre_plugins.<plugin name>.
    actual_plugin = 'calibre_plugins.library_mentor.action:LibraryMentorAction'
