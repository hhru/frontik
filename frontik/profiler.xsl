<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns="http://www.w3.org/1999/xhtml">

    <xsl:output omit-xml-declaration="yes" method="xml" indent="no" encoding="UTF-8" media-type="text/html"/>

    <xsl:variable name="totalTime" select="/profiler/stages/stage[@name='total']/@delta"/>
    <xsl:variable name="warningValue" select="/profiler/options/warning-value/text()"/>
    <xsl:variable name="criticalValue" select="/profiler/options/critical-value/text()"/>

    <xsl:template match="/profiler/stages">
        <xsl:apply-templates select="." mode="css"/>
        <xsl:apply-templates select="." mode="js"/>
        <xsl:variable name="class">
            <xsl:if test="$totalTime >= $warningValue and $totalTime &lt; $criticalValue">warning</xsl:if>
            <xsl:if test="$totalTime >= $criticalValue">critical</xsl:if>
        </xsl:variable>
        <div id="Frontik-Profiler-Component" class="noprint frontik-profiler">
            <span class="frontik-profiler__total_time">
                Время генерации страницы: <span class="{$class}"><xsl:value-of select="$totalTime"/> ms</span>
                <xsl:text disable-output-escaping="yes">&amp;nbsp;</xsl:text>
                <a href="#" id="Frontik-Profiler-Toggle-Table-Button" onclick="return toggleProfilerTable(this)">Подробнее »</a>
            </span>
            <span class="Frontik-Profiler-Button-Close frontik-profiler__button_close" onclick="closeProfiler()">x</span>
            <table id="Frontik-Profiler-Component-Table">
                <xsl:apply-templates select="stage[@name != 'total']"/>
            </table>
        </div>
    </xsl:template>

    <xsl:template match="stage">
        <tr class="frontik-profiler__stage">
            <td class="frontik-profiler__stage_name_cell">
                <a href="#" class="frontik-profiler__stage_name" onclick="return toggleDetailed(this)">
                    <xsl:value-of select="@name"/>
                </a>
            </td>
            <td>
                <xsl:variable name="left" select="100 * @start div $totalTime"/>
                <xsl:variable name="width" select="100 * @delta div $totalTime"/>
                <div class="frontik-profiler__stage_bar" style="left: {$left}%; width: {$width}%">
                    <xsl:attribute name="title">
                        <xsl:value-of select="@delta"/> ms
                    </xsl:attribute>
                    <xsl:text disable-output-escaping="yes">&amp;nbsp;</xsl:text>
                </div>
            </td>
        </tr>
        <tr class="frontik-profiler__stage_info">
            <td colspan="2">Время: <xsl:value-of select="@delta"/> ms</td>
        </tr>
    </xsl:template>

    <xsl:template match="stages" mode="js">
        <script type="text/javascript"><xsl:text disable-output-escaping="yes">

            contentLoaded(window, function() {
                var profiler = document.getElementById('Frontik-Profiler-Component');
                document.body.insertBefore(profiler.parentNode.removeChild(profiler), document.body.firstChild);

                setCookie('debug', 'profile');
                if (getCookie('frontik-profiler') == 'show') {
                    var profilerTable = document.getElementById('Frontik-Profiler-Component-Table');
                    profilerTable.className = profilerTable.className + ' visible';
                    document.getElementById('Frontik-Profiler-Toggle-Table-Button').innerText = 'Скрыть «';
                }
            });

            function closeProfiler() {
                setCookie('debug', '', -1);
                (e=document.getElementById('Frontik-Profiler-Component')).parentNode.removeChild(e);
            }

            function toggleDetailed(e) {
                var detailedInfo = e.parentNode.parentNode.nextSibling;
                if (detailedInfo.className.indexOf('visible') != -1) {
                    detailedInfo.className = detailedInfo.className.replace(/visible/, '');
                } else{
                    detailedInfo.className = detailedInfo.className + ' visible';
                }

                return false;
            }

            function toggleProfilerTable(e) {
                var profilerTable = document.getElementById('Frontik-Profiler-Component-Table');
                if (profilerTable.className.indexOf('visible') != -1) {
                    profilerTable.className = profilerTable.className.replace(/visible/, '');
                    e.innerText = 'Подробнее »';
                    setCookie('frontik-profiler', '', -1);
                } else{
                    profilerTable.className = profilerTable.className + ' visible';
                    e.innerText = 'Скрыть «';
                    setCookie('frontik-profiler', 'show');
                }

                return false;
            }

            function setCookie(name, value, time) {
                var cookie = name + '=' + (value || '') + ';path=/';

                if (typeof(time) != 'undefined') {
                    var expire = new Date();
                    expire.setTime(expire.getTime() + time * 3600000);
                    cookie += ';expires=' + expire.toGMTString();
                }

                document.cookie = cookie;
            }

            function getCookie(name) {
                var kukki = document.cookie;
                var index = kukki.indexOf(name + '=');
                if (index == -1) return null;

                index = kukki.indexOf('=', index) + 1;
                var endstr = kukki.indexOf(';', index);
                if (endstr == -1) {
                    endstr = kukki.length;
                }

                return decodeURIComponent(kukki.substring(index, endstr));
            }

            /*!
            * contentloaded.js
            *
            * Author: Diego Perini (diego.perini at gmail.com)
            * Summary: cross-browser wrapper for DOMContentLoaded
            * Updated: 20101020
            * License: MIT
            * Version: 1.2
            *
            * URL:
            * http://javascript.nwbox.com/ContentLoaded/
            * http://javascript.nwbox.com/ContentLoaded/MIT-LICENSE
            */

            function contentLoaded(win, fn) {
                var done = false, top = true,
                doc = win.document, root = doc.documentElement,
                add = doc.addEventListener ? 'addEventListener' : 'attachEvent',
                rem = doc.addEventListener ? 'removeEventListener' : 'detachEvent',
                pre = doc.addEventListener ? '' : 'on',

                init = function(e) {
                    if (e.type == 'readystatechange' &amp;&amp; doc.readyState != 'complete') return;
                    (e.type == 'load' ? win : doc)[rem](pre + e.type, init, false);
                    if (!done &amp;&amp; (done = true)) fn.call(win, e.type || e);
                },

                poll = function() {
                    try { root.doScroll('left'); } catch(e) { setTimeout(poll, 50); return; }
                    init('poll');
                };

                if (doc.readyState == 'complete') fn.call(win, 'lazy');
                else {
                    if (doc.createEventObject &amp;&amp; root.doScroll) {
                        try { top = !win.frameElement; } catch(e) { }
                        if (top) poll();
                    }
                    doc[add](pre + 'DOMContentLoaded', init, false);
                    doc[add](pre + 'readystatechange', init, false);
                    win[add](pre + 'load', init, false);
                }

            }

        </xsl:text></script>
    </xsl:template>

    <xsl:template match="stages" mode="css">
        <style>

            .frontik-profiler {
                width: 60%;
                margin: 0 auto;
                margin-bottom: 12px;
                padding: 5px 10px;
                border: 1px solid #999;
                border-top: none;
                font-family: Arial, Verdana, Helvetica, sans-serif;
                font-size: 12px;
                background: #fff;
                line-height: 20px;
                -moz-box-shadow: -1px 2px 10px -3px #333;
                box-shadow: -1px 2px 10px -3px #333;
                z-index: 1234567;
            }

                .frontik-profiler__total_time {
                    padding-left: 2px;
                }

                    .frontik-profiler__total_time span {
                        display: inline-block;
                        margin-right: 10px;
                        padding: 0 3px;
                        background: #5bb75b;
                        color: #fff;
                        -webkit-border-radius: 4px;
                        -moz-border-radius: 4px;
                        border-radius: 4px;
                    }

                        .frontik-profiler__total_time span.warning {
                            background: #faa732;
                        }

                        .frontik-profiler__total_time span.critical {
                            background: #da4f49;
                        }

                .frontik-profiler table {
                    display: none;
                    width: 100%;
                    margin-top: 6px;
                    border-collapse: collapse;
                }

                    .frontik-profiler table.visible {
                        display: table;
                    }

                    .frontik-profiler tr:nth-child(4n+1), .frontik-profiler tr:nth-child(4n+2) {
                        background: #eef;
                    }

                    .frontik-profiler__stage_info {
                        display: none;
                    }

                        .frontik-profiler__stage_info.visible {
                            display: table-row;
                        }

                        .frontik-profiler__stage_info td {
                            padding: 0 3px;
                        }

                    .frontik-profiler__stage_name_cell {
                        width: 60px;
                        padding: 0 3px;
                    }

                        .frontik-profiler__stage_name {
                            display: block;
                            width: 60px;
                            text-overflow: ellipsis;
                            overflow: hidden;
                        }

                    .frontik-profiler__stage .frontik-profiler__stage_bar {
                        position: relative;
                        text-align: center;
                        white-space: nowrap;
                        background: #006dcc;
                    }

                .frontik-profiler__button_close {
                    display: block;
                    float: right;
                    margin-top: -1px;
                    padding-right: 3px;
                    text-decoration: none;
                    cursor: pointer;
                }

                    .frontik-profiler__button_close:hover {
                        color: #c00;
                    }

        </style>
    </xsl:template>

</xsl:stylesheet>
