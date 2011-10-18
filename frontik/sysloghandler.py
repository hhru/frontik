import codecs
import socket
import logging

MIN_MSG_LENGTH_LIMIT = 100
STD_MSG_LENGTH_LIMIT = 2048

class SysLogHandler(logging.handlers.SysLogHandler):

    def __init__(self, msg_max_length = STD_MSG_LENGTH_LIMIT, *args, **kwargs):
        if msg_max_length >= MIN_MSG_LENGTH_LIMIT:
            self.max_length = msg_max_length
        else:
            self.max_length = STD_MSG_LENGTH_LIMIT
        super(SysLogHandler, self).__init__(*args, **kwargs)

    def emit(self, record):
        """
        Emit a record.

        The record is formatted, and then sent to the syslog server. If
        exception information is present, it is NOT sent to the server.
        """
        msg = self.format(record) + '\000'
        """
        We need to convert record level to lowercase, maybe this will
        change in the future.
        """
        prio = '<%d>' % self.encodePriority(self.facility,
                                            self.mapPriority(record.levelname))
        if type(msg) is unicode:
            msg = msg.encode('utf-8')
            if codecs:
                msg = codecs.BOM_UTF8 + msg
        msg = prio + msg

        msg = msg[:self.max_length]
        
        try:
            if self.unixsocket:
                try:
                    self.socket.send(msg)
                except socket.error:
                    self._connect_unixsocket(self.address)
                    self.socket.send(msg)
            elif self.socktype == socket.SOCK_DGRAM:
                self.socket.sendto(msg, self.address)
            else:
                self.socket.sendall(msg)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)