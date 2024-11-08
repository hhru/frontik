## Server

В версиях 8.* используется торнадо сервер с конвертацией запросов в asgi интерфейс.

Есть два режима работы: workers = 1 и workers > 1.
В первом случае запускается единый процесс выполняющий все интеграции асинхронно/в тредах.
Во втором случае имеем выделенный мастер процесс и `workers` процессов работников для обработки запросов.
Мастер процесс 1) Подписывается на обновления апстримов в консуле и передает их в воркеров через пайп 2) Супервайзит воркер процессы. 
В большинстве случаев, например оом, просто перезапустит упавшего

Воркер процессы появляются методом fork. Есть возможность передать функцию для выполнения в мастере до форка (см (см [код](../frontik/server.py)))
Это может быть полезно, если необходимо заиспользовать механизм copy on write.
(В питоне copy on write не работает из-за ссылочного gc)