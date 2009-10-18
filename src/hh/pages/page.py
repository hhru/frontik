from hh.http_client import http_get

planetahrHost = 'http://192.168.0.9:9797/'
siteCode = 'hh.ru'
lang = 'RU'

#        xscript.state:setString("token", xscript.request:getCookie("token"));
#        xscript.state:setString("hhtoken", xscript.request:getCookie("hhtoken"));
#        xscript.state:setString("hhid", xscript.request:getCookie("hhid"));
#        xscript.state:setString("hhuid", xscript.request:getCookie("hhuid"));
#        xscript.state:setString("GMT", xscript.request:getCookie("GMT"));
#        local host, foo = string.gsub(xscript.state:get('host'), '\:[0-9]*', '')
#        xscript.state:setString('host', host);

#  <x:mist>
#    <method>setStateConcatString</method>
#    <param type="String">uriSession</param>
#    <param type="StateArg" as="String">sessionHost</param>
#    <param type="String">hh-session?host=</param>
#    <param type="StateArg">host</param>
#    <param type="String">&amp;hhtoken=</param>
#    <param type="StateArg">hhtoken</param>
#    <param type="String">&amp;hhuid=</param>
#    <param type="StateArg">hhuid</param>
#  </x:mist>
#  <x:http>
#    <method>getHttp</method>
#    <threaded>no</threaded>
#    <proxy>true</proxy>
#    <param type="StateArg" as="String">uriSession</param>
#
#    <xpath expr="/session/hhid-session/account/hhid" result="userHhid" />
#    <xpath expr="/session/hhid-session/account/email" result="userEmail" />
#    <xpath expr="/session/hh-session/account/user-id" result="userId" />
#    <xpath expr="/session/hh-session/account/user-type" result="userType" />
#    <xpath expr="/session/locale/lang" result="lang" />
#    <xpath expr="/session/locale/site-id" result="site" />
#    <xpath expr="/session/locale/site-code" result="siteCode" />
#    <xpath expr="/session/locale/platform-code" result="platform" />
#    <xpath expr="/session/locale/area-id" result="area" />
#  </x:http>

def get_session(request):
    token = request.cookies['token']
    hhtoken = request.cookies['hhtoken']
    hhuid = request.cookies['hhuid']
    GMT = request.cookies['GMT']
    
    url = (sessionHost + 'hh-session' + 
           '?host=' + get_host() +
           '&hhtoken=' + hhtoken + 
           '&hhuid=' + hhuid) 

    session_xml = http_get(url)
    
    userHhid = session_xml.xpath('/session/hhid-session/account/hhid').text
    userEmail = session_xml.xpath('/session/hhid-session/account/email').text