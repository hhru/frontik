## Migration guide

### from 7.* to 8.*

1) Extract all handlers from class to module lvl

before:
```python
class Page(PageHandler):
    async def get_page(self):
        ...
```

after:
```python
@router('/url', cls=Page)
async def get_page(handler = get_current_handler()):
    ...
```

2. Rename config `app` to `service_name`


