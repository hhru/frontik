<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:output omit-xml-declaration="yes" method="html" indent="no" encoding="utf-8"/>

    <xsl:include href="debug-css.xsl"/>
    <xsl:include href="highlight-css.xsl"/>
    <xsl:include href="debug-js.xsl"/>
    <xsl:include href="highlight-js.xsl"/>

    <xsl:key name="labels" match="/log/labels/*" use="local-name()"/>

    <xsl:variable name="highlight-text">
        <xsl:if test="contains(/log/@mode, '@')">
            <xsl:value-of select="substring(/log/@mode, 2)"/>
        </xsl:if>
    </xsl:variable>

    <xsl:variable name="total-time">
        <xsl:value-of select="/log/@stages-total"/>
    </xsl:variable>

    <xsl:template match="log">
        <xsl:text disable-output-escaping='yes'>&lt;!DOCTYPE html></xsl:text>
        <html>
            <head>
                <title>Status
                    <xsl:value-of select="@code"/>
                </title>
                <xsl:call-template name="debug-css"/>
                <xsl:call-template name="highlight-css"/>
                <xsl:call-template name="debug-js"/>
                <xsl:call-template name="highlight-js"/>
            </head>
            <body>
                <xsl:apply-templates select="." mode="debug-log"/>
            </body>
        </html>
    </xsl:template>

    <xsl:template match="log" mode="debug-log">
        <xsl:apply-templates select="." mode="timeline"/>

        <div class="entry entry_title">
            request id: <xsl:value-of select="@request-id"/>,
            code: <xsl:value-of select="@code"/><br/>
            requests: <xsl:value-of select="count(entry/response)"/>,
            bytes received: <xsl:value-of select="sum(entry/response/size)"/>,
            bytes produced: <xsl:value-of select="@response-size"/><br/>
            page generated in: <xsl:value-of select="format-number(@stages-total, '#0.##')"/>ms,
            debug generated in: <xsl:value-of select="format-number(@generate-time, '#0.##')"/>ms
        </div>

        <xsl:apply-templates select="." mode="versions-info"/>
        <xsl:apply-templates select="." mode="general-info"/>
        <xsl:apply-templates select="entry[profile]"/>
        <xsl:apply-templates select="entry[not(profile)]"/>
    </xsl:template>

    <xsl:template match="log" mode="timeline"/>

    <xsl:template match="log[ancestor::log]" mode="timeline">
        <xsl:variable name="timeline-offset-number" select="1000 * (../log/@started - /log/@started) div $total-time"/>

        <xsl:variable name="timeline-offset" select="format-number($timeline-offset-number, '##.##%')"/>
        <xsl:variable name="timeline-width" select="format-number(../log/@stages-total div $total-time, '##.##%')"/>

        <xsl:variable name="timeline-debug-offset" select="format-number($timeline-offset-number + ../log/@stages-total div $total-time, '##.##%')"/>
        <xsl:variable name="timeline-debug-width" select="format-number(@generate-time div $total-time, '##.##%')"/>

        <div style="width: {$timeline-width}; left: {$timeline-offset}" class="timeline"/>
        <div style="width: {$timeline-debug-width}; left: {$timeline-debug-offset}" class="timeline timeline_debug"/>
    </xsl:template>

    <xsl:template match="log" mode="versions-info">
        <div class="entry entry_expandable">
            <label for="details_{generate-id(versions)}" onclick="toggle(this.parentNode)" class="entry__head entry__switcher">
                <span class="entry__head__expandtext">
                    Version info
                </span>
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(versions)}"/>
            <div class="details">
                <xsl:call-template name="highlighted-block">
                    <xsl:with-param name="text" select="versions"/>
                </xsl:call-template>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="log" mode="general-info">
        <div class="entry entry_expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="entry__head entry__switcher">
                <span class="entry__head__expandtext">
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
            <xsl:if test="$highlight-text != '' and contains(@msg, $highlight-text)">entry__head_highlight</xsl:if>
        </xsl:variable>

        <div class="entry">
            <div class="entry__head {$highlight} {@levelname}">
                <span class="entry__head__message">
                    <xsl:value-of select="@msg"/>
                </span>
            </div>
            <xsl:apply-templates select="exception"/>
        </div>
        <xsl:apply-templates select="exception/trace"/>
    </xsl:template>

    <xsl:template match="entry[labels/label/text() = 'SQL']">
        <div class="entry entry_expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="entry__head entry__switcher">
                <span class="entry__head__expandtext">
                    <span class="time">
                        <xsl:value-of select="format-number(response/request_time, '#0.#')"/>
                        <xsl:text>ms </xsl:text>
                    </span>
                    <xsl:apply-templates select="labels/label"/>
                    <xsl:text> at </xsl:text>
                    <xsl:value-of select="@pathname" />
                    <xsl:text>.</xsl:text>
                    <xsl:value-of select="@funcName" />
                    <xsl:text>(</xsl:text>
                    <xsl:value-of select="@filename" />
                    <xsl:text>:</xsl:text>
                    <xsl:value-of select="@lineno" />
                    <xsl:text>)</xsl:text>
                </span>
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(.)}"/>
            <div class="details">
                <pre class="entry__head">
                    <code class="sql-debug__message  hljs sql">
                        <xsl:value-of select="@msg"/>
                    </code>
                </pre>
            </div>
        </div>
        <xsl:apply-templates select="exception"/>
    </xsl:template>

    <xsl:template match="entry[stage]">
        <xsl:variable name="stagebar-offset" select="1000 * (../../log/@started - /log/@started)"/>

        <xsl:variable name="stagebar-left">
            <xsl:value-of select="format-number(($stagebar-offset + stage/start_delta) div $total-time, '##.##%')"/>
        </xsl:variable>

        <xsl:variable name="stagebar-width">
            <xsl:value-of select="format-number(stage/delta div $total-time, '##.##%')"/>
        </xsl:variable>

        <div class="line {@levelname}">
            <div class="line__bar line__bar_{@levelname}" style="left: {$stagebar-left}; width: {$stagebar-width}"/>
            <span class="line__label">
                <xsl:value-of select="stage/name"/>:
                <xsl:value-of select="format-number(stage/delta, '##.#')"/>ms
            </span>
        </div>
    </xsl:template>

    <!-- Exceptions -->

    <xsl:template match="exception">
        <pre class="exception">
            <xsl:value-of select="text/text()"/>
        </pre>
    </xsl:template>

    <xsl:template match="exception/trace">
        <div class="entry entry_expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="entry__head entry__switcher">
                <span class="entry__head__expandtext">Exception traceback</span>
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
        <div class="entry entry_expandable trace-locals">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="entry__head entry__switcher">
                <span class="entry__head__expandtext trace-locals__caption">Show/hide locals</span>
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

    <!-- / Exceptions -->

    <xsl:template match="entry[contains(@msg, 'finish group') and not(contains(/log/@mode, 'full'))]"/>

    <xsl:template match="entry[response]">
        <xsl:variable name="status">
            <xsl:if test="response[code &lt; 200 or code >= 300 or error != 'None'] or exception">
                error
            </xsl:if>
        </xsl:variable>

        <xsl:variable name="highlight">
            <xsl:if test="$highlight-text != '' and contains(., $highlight-text)">entry__head_highlight</xsl:if>
        </xsl:variable>

        <xsl:variable name="timebar-offset-time">
            <xsl:value-of select="1000 * (request/start_time/text() - /log/@started)"/>
        </xsl:variable>

        <xsl:variable name="timebar-offset">
            <xsl:value-of select="format-number($timebar-offset-time div $total-time, '##.##%')"/>
        </xsl:variable>

        <xsl:variable name="timebar-details-len">
            <xsl:value-of select="format-number(response/request_time div $total-time, '##.##%')"/>
        </xsl:variable>

        <xsl:variable name="timebar-details-direction">
            <xsl:choose>
                <xsl:when test="($timebar-offset-time div $total-time) > 0.5">
                    <xsl:text>rtl</xsl:text>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:text>ltr</xsl:text>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:variable>

        <xsl:variable name="has-inherited-debug">
            <xsl:if test="debug">details_debug</xsl:if>
        </xsl:variable>

        <div class="entry entry_expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="entry__head entry__switcher {$status} {$highlight}">
                <div class="timebar">
                    <div class="timebar__line" style="left: {$timebar-offset}">
                        <strong class="timebar__head timebar__head_{$status}" style="width: {$timebar-details-len}"/>
                    </div>
                </div>

                <span class="entry__head__expandtext">
                    <span class="time">
                        <xsl:value-of select="format-number(response/request_time, '#0.#')"/>
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
            <div class="details {$has-inherited-debug}">
                <xsl:apply-templates select="." mode="debug-inherited-indicator"/>

                <div class="timebar-details">
                    <div class="timebar__line" style="left: {$timebar-offset}; direction: {$timebar-details-direction}; width: {$timebar-details-len}">
                        <xsl:value-of select="format-number($timebar-offset-time, '#0.##')"/>ms
                        <xsl:text> => </xsl:text>
                        <xsl:value-of select="format-number($timebar-offset-time + response/request_time, '#0.##')"/>ms :
                        <xsl:value-of select="$timebar-details-len"/>
                    </div>
                </div>

                <xsl:apply-templates select="request" mode="copy-as-curl"/>
                <xsl:apply-templates select="debug"/>
                <xsl:apply-templates select="request"/>
                <xsl:apply-templates select="response"/>
                <xsl:apply-templates select="exception"/>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="entry" mode="debug-inherited-indicator"/>

    <xsl:template match="entry[debug]" mode="debug-inherited-indicator">
        <div class="debug-inheritance"/>
    </xsl:template>

    <xsl:template match="label">
        <span class="label" style="background-color: {key('labels', .)/text()}">
            <xsl:value-of select="text()"/>
        </span>
    </xsl:template>

    <xsl:template match="entry[text]">
        <div class="entry entry_expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="entry__head entry__switcher">
                <span class="entry__head__expandtext">
                    <xsl:value-of select="@msg"/>
                </span>
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(.)}"/>
            <pre class="details">
                <xsl:call-template name="highlighted-block">
                    <xsl:with-param name="text" select="text/node()"/>
                </xsl:call-template>
            </pre>
        </div>
    </xsl:template>

    <xsl:template match="request">
        <xsl:apply-templates select="params[param and not(../../debug/log/request/params)]"/>
        <xsl:apply-templates select="headers[header and not(../../debug/log/request/headers)]"/>
        <xsl:apply-templates select="cookies[cookie and not(../../debug/log/request/cookies)]"/>
        <xsl:apply-templates select="body[param]" mode="params"/>
        <xsl:apply-templates select="body[not(param)]"/>
    </xsl:template>

    <xsl:template match="request" mode="copy-as-curl">
        <div class="params">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode); select(this.parentNode)" class="delimeter copy-as-curl-link">
                copy as cURL
            </label>
            <input type="checkbox" class="details-expander" id="details_{generate-id(.)}"/>
            <div>
                <pre class="details copy-as-curl">
                    <xsl:value-of select='curl'/>
                </pre>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="response">
        <xsl:apply-templates select="error"/>
        <xsl:apply-templates select="headers[header and not(../../debug/log/response/headers)]"/>
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

    <xsl:template match="body[text() != '']">
        <div class="delimeter"><xsl:value-of select="name(parent::*)"/> body</div>
        <xsl:call-template name="highlighted-block">
            <xsl:with-param name="mode" select="@mode"/>
            <xsl:with-param name="text" select="."/>
        </xsl:call-template>
    </xsl:template>

    <xsl:template match="body[contains(@content_type, 'text/html') and text() != '']">
        <xsl:variable name="id" select="generate-id(.)"/>
        <div class="delimeter"><xsl:value-of select="name(parent::*)"/> body</div>
        <div id="{$id}"><![CDATA[]]></div>
        <script>
            doiframe('<xsl:value-of select="$id"/>', '<xsl:value-of select="."/>');
        </script>
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

    <!-- Response body highlighting -->

    <xsl:template name="highlighted-block">
        <xsl:param name="mode" select="''"/>
        <xsl:param name="text"/>

        <pre class="body">
            <code class="{$mode}">
                <xsl:value-of select="$text"/>
            </code>
        </pre>
    </xsl:template>

    <!-- / Response body highlighting -->

    <!-- XSLT profiling -->

    <xsl:template match="entry[profile]">
        <div class="entry entry_expandable">
            <label for="details_{generate-id(.)}" onclick="toggle(this.parentNode)" class="entry__head entry__switcher">
                <span class="entry__head__expandtext">XSLT profiling results</span>
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

    <!-- / XSLT profiling -->

</xsl:stylesheet>
