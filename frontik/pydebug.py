import os


def try_init_debugger() -> None:
    debug_setting = os.environ.get('FRONTIK_PY_DEBUG')
    if not debug_setting:
        return

    def _parse_debug_setting(setting: str) -> tuple[bool, int]:
        suspend = setting.startswith('suspend:')
        port = int(setting) if not suspend else int(setting.removeprefix('suspend:'))
        return suspend, port

    if debug_setting.startswith('debugpy:'):
        import debugpy  # noqa: T100

        suspend, port = _parse_debug_setting(debug_setting.removeprefix('debugpy:'))
        debugpy.listen(port)  # noqa: T100
        if suspend:
            debugpy.wait_for_client()  # noqa: T100

    elif debug_setting.startswith('pydevd:'):
        import pydevd_pycharm

        debug_setting = debug_setting.removeprefix('pydevd:')
        host, _, debug_setting = debug_setting.partition(':')
        suspend, port = _parse_debug_setting(debug_setting)
        pydevd_pycharm.settrace(host, port=port, stdout_to_server=True, stderr_to_server=True, suspend=suspend)
