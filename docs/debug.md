## Debug

Фронтик поддерживает несколько режимов дебага, которые можно включить гет-параметром или значением в куке.

debug — выведет обычную дебаг-страницу - можно посмотреть, какие запросы отправляются на бек с данной страницы, заголовки, тела ответов и т.д.
debug=nopass — отключает проброс заголовка X-HH-Debug в другие сервисы
debug=xslt — включает и показывает xslt-профилировщик
notpl — отключает шаблонизацию (noxsl — старый алиас, работающий только для xslt)
notrl — отключает постпроцессор, отвечающий за переводы.

Удобные закладки в браузер

Включить дебаг
```
javascript:document.cookie="debug=true;path=/;"
```

Выключить дебаг
```
javascript:var expire = new Date();expire.setTime(expire.getTime() - 1);document.cookie="debug=true;path=/;expires="+expire.toGMTString();void 0
```

Отключить xslt трансформацию
```
javascript:document.cookie="notpl=true;path=/;";
```

Включить xslt транформацию
```
javascript:document.cookie='notpl=true; max-age=0; path=/;';
```

Отключить переводы
```
javascript:document.cookie='notrl=true; path=/;';
```

Включить переводы
```
javascript:document.cookie='notrl=true; max-age=0; path=/;';
```

