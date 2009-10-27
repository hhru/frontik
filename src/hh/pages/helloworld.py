from frontik import DocResponse

def get_page(request):
    response = DocResponse('hello')
    
    response.doc.put('Hello world!')
    
    return response