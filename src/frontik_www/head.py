from frontik import http_get
from frontik import etree as et

import frontik_www.config

topmenu = et.fromstring('''<topmenu>
  <item>
    <href>employer.xml</href>
    <text>contents.footer.employers</text>
  </item>
  <item>
    <href>applicant.xml</href>
    <text>contents.footer.applicants</text>
  </item>
  <item>
    <href>agency.xml</href>
    <text>contents.footer.agencyes</text>
  </item>
</topmenu>''')

sites = et.fromstring('''<sites>
  <site code="hh.ru">
    <areaId>113</areaId>
    <name>header.region.site.hh.ru</name>
    <site code="hh.ru">
      <areaId>1</areaId>
      <name>header.region.site.moscow.hh.ru</name>
    </site>
    <site code="spb.hh.ru">
      <areaId>231</areaId>
      <name>header.region.site.spb.hh.ru</name>
    </site>
    <site code="voronezh.hh.ru">
      <areaId>230</areaId>
      <name>header.region.site.voronezh.hh.ru</name>
    </site>
    <site code="kazan.hh.ru">
      <areaId>227</areaId>
      <name>header.region.site.kazan.hh.ru</name>
    </site>
    <site code="krasnodar.hh.ru">
      <areaId>224</areaId>
      <name>header.region.site.krasnodar.hh.ru</name>
    </site>
    <site code="krasnoyarsk.hh.ru">
      <areaId>221</areaId>
      <name>header.region.site.krasnoyarsk.hh.ru</name>
    </site>
    <site code="nn.hh.ru">
      <areaId>228</areaId>
      <name>header.region.site.nn.hh.ru</name>
    </site>
    <site code="novosibirsk.hh.ru">
      <areaId>222</areaId>
      <name>header.region.site.novosibirsk.hh.ru</name>
    </site>
    <site code="rostov.hh.ru">
      <areaId>225</areaId>
      <name>header.region.site.rostov.hh.ru</name>
    </site>
    <site code="samara.hh.ru">
      <areaId>226</areaId>
      <name>header.region.site.samara.hh.ru</name>
    </site>
    <site code="ural.hh.ru">
      <areaId>223</areaId>
      <name>header.region.site.ural.hh.ru</name>
    </site>
    <site code="yaroslavl.hh.ru">
      <areaId>229</areaId>
      <name>header.region.site.yaroslavl.hh.ru</name>
    </site>
  </site>
  <site code="hh.ua">
    <areaId>5</areaId>
    <name>header.region.site.hh.ua</name>
    <site code="kiev.hh.ua">
      <areaId>20</areaId>
      <name>header.region.site.kiev.hh.ua</name>
    </site>
    <site code="dnepropetrovsk.hh.ua">
      <areaId>22</areaId>
      <name>header.region.site.dnepropetrovsk.hh.ua</name>
    </site>
    <site code="donetsk.hh.ua">
      <areaId>21</areaId>
      <name>header.region.site.donetsk.hh.ua</name>
    </site>
    <site code="lviv.hh.ua">
      <areaId>25</areaId>
      <name>header.region.site.lviv.hh.ua</name>
    </site>
    <site code="odessa.hh.ua">
      <areaId>24</areaId>
      <name>header.region.site.odessa.hh.ua</name>
    </site>
    <site code="kharkov.hh.ua">
      <areaId>23</areaId>
      <name>header.region.site.kharkov.hh.ua</name>
    </site>
  </site>
  <site code="hh.by">
    <areaId>16</areaId>
    <name>header.region.site.hh.by</name>
  </site>
  <site code="headhunter.com.kz">
    <areaId>40</areaId>
    <name>header.region.site.headhunter.com.kz</name>
  </site>
</sites>
''')

def do_head(handler):
    handler.doc.put(topmenu)
    handler.doc.put(sites)
    
    handler.doc.put(handler.fetch_url(frontik_www.config.serviceHost + 'regionalSiteList?site=' + str(handler.session.site_id)))
    
    handler.doc.put(handler.fetch_url(frontik_www.config.searchHost + 'globalStatistics'))