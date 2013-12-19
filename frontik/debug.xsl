<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" id="style" xmlns:str="http://exslt.org/strings"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:output omit-xml-declaration="yes" method="html" indent="no" encoding="utf-8"/>

    <xsl:key name="labels" match="/log/labels/*" use="local-name()"/>

    <xsl:variable name="highlight-text">
        <xsl:if test="contains(/log/@mode, '@')">
            <xsl:value-of select="substring(/log/@mode, 2)"/>
        </xsl:if>
    </xsl:variable>
    <xsl:variable name="total-time">
        <xsl:value-of select="/log/stages/stage[@name='total']"/>
    </xsl:variable>

    <xsl:template match="log">
        <xsl:text disable-output-escaping='yes'>&lt;!DOCTYPE html></xsl:text>
        <html>
            <head>
                <title>Status
                    <xsl:value-of select="@code"/>
                </title>
                <xsl:apply-templates select="." mode="css"/>
                <xsl:apply-templates select="." mode="js"/>
            </head>
            <body>
                <xsl:apply-templates select="." mode="debug-log"/>
            </body>
        </html>
    </xsl:template>

    <xsl:template match="log" mode="debug-log">
        <div class="textentry m-textentry_title">
            requestid: <xsl:value-of select="@request-id"/>,
            status: <xsl:value-of select="@code"/>,
            requests: <xsl:value-of select="count(entry/response)"/>,
            bytes received: <xsl:value-of select="sum(entry/response/size)"/>,
            bytes produced: <xsl:value-of select="@response-size"/>,
            debug generated in: <xsl:value-of select="format-number(@generate-time, '#0.##')"/>ms
        </div>

        <xsl:apply-templates select="." mode="versions-info"/>
        <xsl:apply-templates select="." mode="general-info"/>
        <xsl:apply-templates select="entry[profile]"/>
        <xsl:apply-templates select="entry[not(profile)]"/>
    </xsl:template>

    <xsl:template match="entry[contains(@msg, 'finish group') and not(contains(/log/@mode, 'full'))]"/>

    <xsl:template match="log" mode="versions-info">
        <div class="textentry m-textentry__expandable">
            <label for="details_{generate-id(versions)}" onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher">
                <span class="textentry__head__expandtext">
                    Version info
                </span>
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(versions)}"/>
            <div class="details">
                <xsl:apply-templates select="versions/node()" mode="color-xml"/>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="log" mode="general-info">
        <div class="textentry m-textentry__expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher">
                <span class="textentry__head__expandtext">
                    General request/response info
                </span>
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(.)}"/>
            <div class="details">
                <xsl:apply-templates select="request/params"/>
                <xsl:apply-templates select="request/headers"/>
                <xsl:apply-templates select="request/cookies"/>
                <xsl:apply-templates select="response/headers"/>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="entry">

        <xsl:variable name="highlight">
            <xsl:if test="$highlight-text != '' and contains(@msg, $highlight-text)">m-textentry__head_highlight</xsl:if>
        </xsl:variable>

        <xsl:variable name="loglevel">
            <xsl:value-of select="@levelname"/>
        </xsl:variable>

        <xsl:variable name="time-offset">
            <xsl:value-of select="1000* (@created - /log/@started)"/>
        </xsl:variable>
            
        <div class="textentry">
            <div class="textentry__head {$highlight} {$loglevel}">
                <span class="textentry__head__message">
                    <xsl:value-of select="concat($loglevel,' ',@msg)"/>
                </span>
            </div>
            <xsl:apply-templates select="exception"/>
        </div>
        <xsl:apply-templates select="exception/trace"/>
    </xsl:template>

    <xsl:template match="exception">
        <pre class="exception">
            <xsl:value-of select="text/text()"/>
        </pre>
    </xsl:template>

    <xsl:template match="exception/trace">
        <div class="textentry m-textentry__expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher">
                <span class="textentry__head__expandtext">Exception traceback</span>
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(.)}"/>
            <div class="details">
                <xsl:apply-templates select="step"/>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="step">
        <pre class="trace-file">
            <xsl:value-of select="file"/>
        </pre>
        <div class="textentry m-textentry__expandable trace-locals">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher">
                <span class="trace-locals__caption">Show/hide locals</span>
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(.)}"/>
            <div class="details">
                <pre class="trace-locals__text">
                    <xsl:value-of select="locals/text()"/>
                </pre>
            </div>
        </div>
        <table class="trace-lines">
            <tr>
                <xsl:apply-templates select="lines[not(line)]"/>
                <td class="trace-lines__column"><xsl:apply-templates select="lines/line/number"/></td>
                <td class="trace-lines__column"><xsl:apply-templates select="lines/line/text"/></td>
            </tr>
        </table>
    </xsl:template>

    <xsl:template match="lines[not(line)]">
        <td>Unable to find source file</td>
    </xsl:template>

    <xsl:template match="line/number|line/text">
        <span class="trace-lines__line">
            <xsl:if test="../@selected = 'true'">
                <xsl:attribute name="class">trace-lines__line selected</xsl:attribute>
            </xsl:if>
            <xsl:value-of select="."/>
        </span>
    </xsl:template>

    <xsl:template match="entry[contains(@msg, 'finish group') and not(contains(/log/@mode, 'full'))]"/>

    <xsl:template match="entry[response]">
        <xsl:variable name="status">
            <xsl:if test="response/code != 200">error</xsl:if>
        </xsl:variable>
        <xsl:variable name="highlight">
            <xsl:if test="$highlight-text != '' and contains(., $highlight-text)">m-textentry__head_highlight</xsl:if>
        </xsl:variable>

        <xsl:variable name="timebar-offset">
            <xsl:value-of select="1000 * (request/meta/start_time/text() - /log/@started)"/>
        </xsl:variable>
        
        <xsl:variable name="timebar-percent-offset">
            <xsl:value-of select="format-number($timebar-offset div $total-time, '##.#%')"/>
        </xsl:variable>

        <xsl:variable name="timebar-details-percent-width">
            <xsl:value-of select="format-number(1 - ($timebar-offset div $total-time), '##.#%')"/>
        </xsl:variable>

        <xsl:variable name="timebar-len-percent">
            <xsl:value-of select="format-number(response/request_time div $total-time, '##.#%')"/>
        </xsl:variable>

        <div class="textentry m-textentry__expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher {$status} {$highlight}">
                <div class="timebar">
                    <div class="timebar__line" style="left: {$timebar-percent-offset}">
                        <strong class="timebar__head timebar__head_{$status}" style="width: {$timebar-len-percent};"></strong>
                    </div>
                </div>
                <span class="textentry__head__expandtext">
                    <span class="time">
                        <xsl:value-of select="response/request_time"/>
                        <xsl:text>ms </xsl:text>
                    </span>
                    <xsl:apply-templates select="labels/label"/>
                    <xsl:value-of select="response/code"/>
                    <xsl:text> </xsl:text>
                    <xsl:value-of select="request/method"/>
                    <xsl:text> </xsl:text>
                    <xsl:value-of select="format-number(response/size div 1024, '0.#')"/>
                    <xsl:text>Kb </xsl:text>
                    <xsl:value-of select="request/url"/>
                </span>
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(.)}"/>
            <div class="details">
                <div class="timebar-details">
                    <div class="timebar__line" style="left: {$timebar-percent-offset}; width: {$timebar-details-percent-width}">
                        [<xsl:value-of select="format-number($timebar-offset, '#0.##')"/>ms
                        <xsl:text> => </xsl:text>
                        <xsl:value-of select="format-number($timebar-offset + response/request_time, '#0.##')"/>ms] :
                        <xsl:value-of select="$timebar-len-percent"/>
                    </div>
                </div>
                <xsl:apply-templates select="debug"/>
                <xsl:apply-templates select="request"/>
                <xsl:apply-templates select="response"/>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="label">
        <span class="label" style="background-color: {key('labels', .)/text()}">
            <xsl:value-of select="text()"/>
        </span>
    </xsl:template>

    <xsl:template match="entry[xml]">
        <div class="textentry m-textentry__expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher">
                <span class="textentry__head__expandtext">
                    <xsl:value-of select="@msg"/>
                </span>
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(.)}"/>
            <div class="details">
                <xsl:apply-templates select="xml/node()" mode="color-xml"/>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="entry[protobuf]">
        <div class="textentry m-textentry__expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher">
                <span class="textentry__head__expandtext">
                    <xsl:value-of select="@msg"/>
                </span>
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(.)}"/>
            <pre class="details">
                <xsl:apply-templates select="protobuf/node()" mode="color-xml"/>
            </pre>
        </div>
    </xsl:template>

    <xsl:template match="request">
        <div>
            <a class="servicelink" href="{url}" target="_blank">
                <xsl:value-of select="url"/>
            </a>
        </div>
        <xsl:apply-templates select="headers[header]"/>
        <xsl:apply-templates select="cookies[cookie]"/>
        <xsl:apply-templates select="params[param]"/>
        <xsl:apply-templates select="body[param]" mode="params"/>
        <xsl:apply-templates select="body[not(param)]"/>
    </xsl:template>

    <xsl:template match="response">
        <xsl:apply-templates select="error"/>
        <xsl:apply-templates select="headers[header]"/>
        <xsl:apply-templates select="body"/>
    </xsl:template>

    <xsl:template match="debug">
        <div class="debug-inherited">
            <xsl:apply-templates select="." mode="debug-log"/>
        </div>
    </xsl:template>

    <xsl:template match="error[text() = 'None']"/>

    <xsl:template match="error">
        <div class="delimeter">error code</div>
        <div class="error"><xsl:value-of select="."/></div>
    </xsl:template>

    <xsl:template match="body"/>

    <xsl:template match="body[text()]">
        <div class="delimeter"><xsl:value-of select="name(parent::*)"/> body</div>
        <pre class="body">
            <xsl:value-of select="."/>
        </pre>
    </xsl:template>

    <xsl:template match="body[*]">
        <div class="delimeter"><xsl:value-of select="name(parent::*)"/> body</div>
        <div class="coloredxml">
            <xsl:apply-templates select="node()" mode="color-xml"/>
        </div>
    </xsl:template>

    <xsl:template match="body[contains(@content_type, 'text/html') and text() != '']">
        <xsl:variable name="id" select="generate-id(.)"/>
        <div class="delimeter"><xsl:value-of select="name(parent::*)"/> body</div>
        <div id="{$id}"><![CDATA[]]></div> 
        <script>
            doiframe('<xsl:value-of select="$id"/>', '<xsl:value-of select="."/>');
        </script>
    </xsl:template>

    <xsl:template match="body[contains(@content_type, 'json') and text() != '']">
        <div class="delimeter"><xsl:value-of select="name(parent::*)"/> body</div>
        <pre><xsl:value-of select="."/></pre>
    </xsl:template>

    <xsl:template match="body[text() = '']">
        <div class="delimeter"><xsl:value-of select="name(parent::*)"/> body</div>
        Empty response
    </xsl:template>

    <xsl:template match="body" mode="params">
        <div class="params">
            <div class="delimeter">request body</div>
            <xsl:apply-templates select="param"/>
        </div>
    </xsl:template>

    <xsl:template match="headers[header]">
        <div class="headers">
            <div class="delimeter"><xsl:value-of select="name(parent::*)"/> headers</div>
            <xsl:apply-templates select="header"/>
        </div>
    </xsl:template>

    <xsl:template match="header">
        <div><xsl:value-of select="@name"/>: &#160;<xsl:value-of select="."/></div>
    </xsl:template>

    <xsl:template match="cookies[cookie]">
        <div class="cookies">
            <div class="delimeter">cookies</div>
            <xsl:apply-templates select="cookie"/>
        </div>
    </xsl:template>

    <xsl:template match="cookie">
        <div><xsl:value-of select="@name"/>&#160;=&#160;<xsl:value-of select="."/></div>
    </xsl:template>

    <xsl:template match="params[param]">
        <div class="params">
            <div class="delimeter">request params</div>
            <xsl:apply-templates select="param"/>
        </div>
    </xsl:template>

    <xsl:template match="param">
        <div>
            <xsl:value-of select="@name"/><xsl:text>&#160;=&#160;</xsl:text><xsl:value-of select="."/>
        </div>
    </xsl:template>

    <!-- XSLT profiling -->

    <xsl:template match="entry[profile]">
        <div class="textentry m-textentry__expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher">
                <span class="textentry__head__expandtext">XSLT profiling results</span>
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(.)}" checked="checked"/>
            <div class="details m-details_visible">
                <xsl:apply-templates select="profile" mode="xslt-profile"/>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="profile" mode="xslt-profile">
        <table class="xslt-profile">
            <thead><tr>
                <xsl:apply-templates select="template[1]/@*[name()!='rank']" mode="xslt-profile"/>
            </tr></thead>
            <tbody>
                <xsl:apply-templates select="template" mode="xslt-profile"/>
            </tbody>
        </table>
    </xsl:template>

    <xsl:template match="@*" mode="xslt-profile">
        <th class="xslt-profile-header">
            <xsl:value-of select="name()"/>
        </th>
    </xsl:template>

    <xsl:template match="@*[name()='time']" mode="xslt-profile">
        <th class="xslt-profile-header xslt-profile-header__sortable" onclick="sortTableColumn(this.parentNode.parentNode.parentNode, this.cellIndex)" title="Sort by this field">
            <xsl:value-of select="name()"/>
            [total <xsl:value-of select="format-number(sum(ancestor::profile/template/@time) div 100, '#.##')"/>]
            <xsl:apply-templates select="." mode="xslt-profile-units"/>
        </th>
    </xsl:template>

    <xsl:template match="@*[name()='calls' or name()='average']" mode="xslt-profile">
        <th class="xslt-profile-header xslt-profile-header__sortable" onclick="sortTableColumn(this.parentNode.parentNode.parentNode, this.cellIndex)" title="Sort by this field">
            <xsl:value-of select="name()"/>
            <xsl:apply-templates select="." mode="xslt-profile-units"/>
        </th>
    </xsl:template>

    <xsl:template match="@*" mode="xslt-profile-units"/>

    <xsl:template match="@*[name()='time' or name()='average']" mode="xslt-profile-units">
        (ms)
    </xsl:template>

    <xsl:template match="template" mode="xslt-profile">
        <tr class="xslt-profile-row">
            <xsl:apply-templates select="@*[name()!='rank']" mode="xslt-profile-item"/>
        </tr>
    </xsl:template>

    <xsl:template match="@*[name()='match' or name()='name' or name()='mode']" mode="xslt-profile-item">
        <td class="xslt-profile-item xslt-profile-item__text"><xsl:value-of select="."/></td>
    </xsl:template>

    <xsl:template match="@*[name()='calls']" mode="xslt-profile-item">
        <td class="xslt-profile-item xslt-profile-item__number">
            <xsl:value-of select="."/>
        </td>
    </xsl:template>

    <xsl:template match="@*" mode="xslt-profile-item">
        <td class="xslt-profile-item xslt-profile-item__number">
            <xsl:value-of select="format-number(. div 100, '#.##')"/>
        </td>
    </xsl:template>


    <xsl:template match="log" mode="css">
        <style>
            body { margin: 0 10px; }
            body, pre {
                font-family: sans-serif;
            }
            pre {
                margin: 0;
                white-space: pre-wrap;
            }
            .body {
                word-break: break-all;
            }

            .timebar {
                width: 100%;
                margin-bottom: -1.4em;
                position: relative;
            }
                .timebar__line {
                    position: relative;
                    vertical-align: middle;
                }
                .timebar__head {
                    border-left: 1px solid green;
                    border-right: 1px solid green;
                    background-color: #94b24d;
                    border-bottom: 1px solid #94b24d;
                    opacity: 0.5;
                    display: block;
                    width: 0;
                    height: 1.4em;
                }
                    .timebar__head_error {
                        background-color: red;
                    }
            .timebar-details {
                left: 0;
                top: 0;
                height: 100%;
                width: 100%;
            }

            .textentry {
                padding-left: 20px;
                padding-right: 20px;
                margin-bottom: 4px;
                word-break: break-all;
                position: relative;
            }
                .m-textentry__expandable {
                    background: #fffccf;
                }
                .m-textentry_title {
                    font-size: 1.3em;
                    margin-bottom: .5em;
                }
                .textentry__head {
                    display: block;
                }
                    .m-textentry__head_highlight {
                        font-weight: bold;
                    }
                    .textentry__head__expandtext {
                        border-bottom: 1px dotted #666;
                        display: inline-block;
                        position: relative;
                        vertical-align: bottom;
                        line-height: 1.4em;
                        margin-top: -1px;
                    }
                    .textentry__head__message {
                        white-space: pre;
                    }
                .textentry__switcher {
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                    cursor: pointer;
                }
            .headers{
            }
            .details-expander {
                display: none;
            }
            .details {
                display: none;
                padding-bottom: 2px;
                position: relative;
            }
                .m-details_visible,
                .details-expander:checked + .details {
                    display:block;
                }

            .servicelink {
                color: #666;
                font-size: .8em;
            }
            .coloredxml__line {
                padding: 0px 0px 0px 20px;
            }
            .coloredxml__tag, .coloredxml__param {
                color: #9c0628;
            }
            .coloredxml__comment {
                color: #063;
                display: block;
                padding: 0px 0px 0px 30px;
                padding-top: 20px;
            }
            .time {
                display: inline-block;
                width: 4em;
            }
            .label {
                margin-right: 8px;
                padding: 0 3px;
                font-size: 14px;
                border-radius: 5px;
            }
            .error {
                color: red;
            }
            .ERROR {
                color: #c00;
            }
            .WARNING {
                color: #E80;
            }
            .INFO {
                color: #060;
            }
            .DEBUG {
                color: #00B;
            }
            .delimeter {
                margin-top: 10px;
                font-size: .8em;
                color: #999;
            }

            .trace-file {
                margin-top: 12px;
                padding: 1px 4px;
                background: #e0e0ff;
            }
            .trace-locals {
                margin-top: 8px;
                margin-left: 12px;
                margin-bottom: 0;
                padding: 0;
                padding-top: 2px;
            }
                .trace-locals__caption {
                    display: inline-block;
                    border-bottom: 1px dashed #000;
                }
                .trace-locals__text {
                    margin-top: 10px;
                    margin-left: 12px;
                    padding: 4px;
                    background: #fff;
                    font-family: monospace;
                }
            .trace-lines {
                margin: 10px 0;
                margin-left: 12px;
                padding: 4px;
                border-collapse: collapse;
                background: #fff;
            }
                .trace-lines__column {
                    margin: 0;
                    padding: 2px 4px;
                }
                .trace-lines__line {
                    display: block;
                    padding: 1px 0;
                    font-family: monospace;
                    white-space: pre;
                    clear: both;
                }
                    .trace-lines__line.selected {
                        color: #c00;
                    }
            .exception {
                color: #c00;
            }

            .iframe {
                width: 100%;
                height: 500px;
                background: #fff;
                border: 1px solid #ccc;
                margin-top: 5px;
                box-shadow: 1px 1px 8px #aaacca;
                -moz-box-shadow: 1px 1px 8px #aaacca;
                -webkit-box-shadow: 1px 1px 8px #aaacca;
            }

            .debug-inherited {
                margin: 10px 0;
                padding: 10px;
                border: 1px solid #ccc;
                background: #fff;
            }

            .xslt-profile {
                margin: 8px 0;
                background: #fff;
            }
                .xslt-profile-row:hover {
                    background: #eee;
                }
                    .xslt-profile-item, .xslt-profile-header {
                        padding: 4px 8px;
                        background: #f5f5ff;
                    }
                    .xslt-profile-header {
                        background: #ddf;
                    }
                        .xslt-profile-header__sortable:hover {
                            text-decoration: underline;
                            cursor: pointer;
                        }
                    .xslt-profile-item__text {
                        width: 20%;
                        text-align: left;
                    }
                    .xslt-profile-item__number {
                        width: 10%;
                        text-align: right;
                    }
        </style>
    </xsl:template>

    <xsl:template match="log" mode="js">
        <script><![CDATA[
            function toggle(entry) {
                var details = entry.querySelector('.details');
                if (details.className.indexOf('m-details_visible') != -1) {
                    details.className = details.className.replace(/\bm-details_visible\b/, '');
                } else {
                    details.className = details.className + ' m-details_visible';
                }
            }

            function doiframe(id, text) {
                var iframe = window.document.createElement('iframe');
                iframe.className = 'iframe'
                var html = text
                    .replace(/&lt;/g, '<')
                    .replace(/&gt;/g, '>')
                    .replace(/&amp;/g, '&');
                window.document.getElementById(id).appendChild(iframe);
                var document = iframe.contentWindow.document;
                document.open();
                document.write(html);
                //document.close();
            }

            function sortTableColumn(table, columnIndex) {
                var rows = [];
                var tBody = table.tBodies[0];

                for (var i = 0; i < tBody.rows.length; i++) {
                    rows.push(tBody.rows[i]);
                }

                function cellText(row, index) {
                    return row.cells[index].textContent || row.cells[index].innerText;
                }

                rows = rows.sort(function(a, b) {
                    var v1 = parseFloat(cellText(a, columnIndex)),
                        v2 = parseFloat(cellText(b, columnIndex));

                    if (v1 == v2) {
                        var s1 = cellText(a, 0) + cellText(a, 1) + cellText(a, 2),
                            s2 = cellText(b, 0) + cellText(b, 1) + cellText(b, 2);
                        return s1 <= s2 ? 1 : -1;
                    }

                    return v1 < v2 ? 1 : -1;
                });

                while (tBody.rows.length > 0) {
                    tBody.deleteRow(0);
                }
                for (var i = 0; i < rows.length; i++) {
                    tBody.appendChild(rows[i]);
                }
            }
        ]]></script>
    </xsl:template>

    <xsl:template match="*" mode="color-xml">
        <div class="coloredxml__line">
            <xsl:text>&lt;</xsl:text>
            <span class="coloredxml__tag">
                <xsl:value-of select="name()"/>
            </span>

            <xsl:for-each select="@*">
                <xsl:text> </xsl:text>
                <span class="coloredxml__param">
                    <xsl:value-of select="name()"/>
                </span>
                <xsl:text>="</xsl:text>
                <span class="coloredxml__value">
                    <xsl:if test="not(string-length(.))">
                        <xsl:text> </xsl:text>
                    </xsl:if>
                    <xsl:value-of select="."/>
                </span>
                <xsl:text>"</xsl:text>
            </xsl:for-each>

            <xsl:choose>
                <xsl:when test="node()">
                    <xsl:text>&gt;</xsl:text>
                    <xsl:apply-templates select="node()" mode="color-xml"/>
                    <xsl:text>&lt;/</xsl:text>
                    <span class="coloredxml__tag">
                        <xsl:value-of select="name()"/>
                    </span>
                    <xsl:text>&gt;</xsl:text>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:text>/&gt;</xsl:text>
                </xsl:otherwise>
            </xsl:choose>
        </div>
    </xsl:template>

    <xsl:template match="text()" mode="color-xml">
        <span class="coloredxml__value">
            <xsl:apply-templates select="str:tokenize(string(.), '&#0013;&#0010;')" mode="line"/>
        </span>
    </xsl:template>

    <xsl:template match="token[text() != '']" mode="line">
        <xsl:if test="position() != 1">
            <br/>
        </xsl:if>
        <xsl:value-of select="."/>
    </xsl:template>

    <xsl:template match="comment()" mode="color-xml">
        <span class="coloredxml__comment">
            &lt;!--<xsl:value-of select="."/>--&gt;
        </span>
    </xsl:template>
</xsl:stylesheet>
