## Testing

Модуль `frontik.testing` содержит удобные классы для поднятия приложения в юнит тестах

Можно инициализировать свое приложение или создать тестовое, дефолт FrontikApplication

```python
import pytest
from frontik.testing import FrontikTestBase
from my_service import MyApplication

class TestFrontikTesting(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self):
        return MyApplication()
    
    async def test_some_page(self):
        response = await self.fetch('/some_page')
        assert response.status_code == 200
```

Можно создавать тест контроллеры рядом с тестом

```python
import pytest
from frontik.routing import router
from frontik.testing import FrontikTestBase

@router.get('/config')
async def config_page() -> str:
    return 'config'


class TestFrontikTesting(FrontikTestBase):
    async def test_config(self):
        response = await self.fetch('/config')
        assert response.status_code == 200
```

