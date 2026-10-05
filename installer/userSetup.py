# NodeX module startup: Maya runs every userSetup.py on sys.path, this one included.
import maya.utils


def _nodex_startup():
    try:
        import nodex.startup
        nodex.startup.run()
    except Exception as e:
        print("NodeX: startup failed: %s" % e)


maya.utils.executeDeferred(_nodex_startup)
