from frontik.routing import router


@router.get('/single_page')
def single_page():
    return 'single_page'
