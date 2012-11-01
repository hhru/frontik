<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" id="style" xmlns:str="http://exslt.org/strings"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:output omit-xml-declaration="yes" method="xml" indent="no" encoding="UTF-8"
                media-type="text/html" doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"
                doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN" version="1.1"/>

    <xsl:variable name="highlight-text">
        <xsl:if test="contains(/log/@mode, '@')">
            <xsl:value-of select="substring(/log/@mode, 2)"/>
        </xsl:if>
    </xsl:variable>

    <xsl:template match="log">
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
            bytes produced: <xsl:value-of select="@response-size"/>
        </div>

        <xsl:apply-templates select="." mode="versions-info"/>
        <xsl:apply-templates select="." mode="general-info"/>
        <xsl:apply-templates select="entry"/>
    </xsl:template>

    <xsl:template match="entry[contains(@msg, 'finish group') and /log/@mode != 'full']"/>

    <xsl:template match="log" mode="versions-info">
        <div class="textentry m-textentry__expandable">
            <div onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher">
                <span class="textentry__head__expandtext">
                    Version info
                </span>
            </div>
            <div class="details">
                <xsl:apply-templates select="versions/node()" mode="color-xml"/>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="log" mode="general-info">
        <div class="textentry m-textentry__expandable">
            <div onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher">
                <span class="textentry__head__expandtext">
                    General request/response info
                </span>
            </div>
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

        <div class="textentry">
            <div class="textentry__head {$highlight} {$loglevel}">
                <span title="{@msg}">
                    <xsl:value-of select="concat($loglevel,' ',@msg)"/>
                </span>
            </div>
            <xsl:apply-templates select="@exc_text"/>
        </div>
    </xsl:template>

    <xsl:template match="@exc_text">
        <pre class="exception">
            <xsl:value-of select="."/>
        </pre>
    </xsl:template>

    <xsl:template match="entry[response]">
        <xsl:variable name="status">
            <xsl:if test="response/code != 200">error</xsl:if>
        </xsl:variable>
        <xsl:variable name="text">
            <xsl:value-of select="."/>
        </xsl:variable>
        <xsl:variable name="highlight">
            <xsl:if test="$highlight-text != '' and contains($text, $highlight-text)">m-textentry__head_highlight
            </xsl:if>
        </xsl:variable>

        <div class="textentry m-textentry__expandable">
            <div onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher {$status} {$highlight}">
                <span title="{@msg}" class="textentry__head__expandtext">
                    <span class="time">
                        <xsl:value-of select="response/request_time"/>
                        <xsl:text>ms </xsl:text>
                    </span>
                    <xsl:value-of select="response/code"/>
                    <xsl:text> </xsl:text>
                    <xsl:value-of select="request/method"/>
                    <xsl:text> </xsl:text>
                    <xsl:value-of select="format-number(response/size div 1024, '0.#')"/>
                    <xsl:text>Kb </xsl:text>
                    <xsl:value-of select="request/url"/>
                </span>
            </div>
            <div class="details">
                <xsl:apply-templates select="debug"/>
                <xsl:apply-templates select="request"/>
                <xsl:apply-templates select="response"/>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="entry[xml]">
        <div class="textentry m-textentry__expandable">
            <div onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher">
                <span title="{@msg}" class="textentry__head__expandtext">
                    <xsl:value-of select="@msg"/>
                </span>
            </div>
            <div class="details">
                <xsl:apply-templates select="xml/node()" mode="color-xml"/>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="entry[protobuf]">
        <div class="textentry m-textentry__expandable">
            <div onclick="toggle(this.parentNode)" class="textentry__head textentry__switcher">
                <span title="{@msg}" class="textentry__head__expandtext">
                    <xsl:value-of select="@msg"/>
                </span>
            </div>
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
        <div class="error">
            <xsl:value-of select="."/>
        </div>
    </xsl:template>

    <xsl:template match="body"/>

    <xsl:template match="body[text()]">
        <div class="delimeter">body</div>
        <div class="body">
            <xsl:value-of select="."/>
        </div>
    </xsl:template>

    <xsl:template match="body[node()]">
        <div class="delimeter">body</div>
        <div class="coloredxml">
            <xsl:apply-templates select="node()" mode="color-xml"/>
        </div>
    </xsl:template>

    <xsl:template match="body[contains(@content_type, 'text/html') and text() != '']">
        <xsl:variable name="id" select="generate-id(.)"/>
        <div class="delimeter">body</div>
        <div id="{$id}"><![CDATA[]]></div>
        <script>
            doiframe('<xsl:value-of select="$id"/>', '<xsl:value-of select="."/>');
        </script>
    </xsl:template>

    <xsl:template match="body[contains(@content_type, 'text/html') and text() = '']">
        <div class="delimeter">body</div>
        Empty response
    </xsl:template>

    <xsl:template match="body[contains(@content_type, 'json')]">
        <div class="delimeter">body</div>
        <pre><xsl:value-of select="."/></pre>
    </xsl:template>

    <xsl:template match="body" mode="params">
        <div class="params">
            <div class="delimeter">body</div>
            <xsl:apply-templates select="param"/>
        </div>
    </xsl:template>

    <xsl:template match="headers">
        <div class="headers">
            <div class="delimeter">headers</div>
            <xsl:apply-templates select="header"/>
        </div>
    </xsl:template>

    <xsl:template match="header">
        <div><xsl:value-of select="@name"/>: &#160;<xsl:value-of select="."/>
        </div>
    </xsl:template>

    <xsl:template match="cookies">
        <div class="cookies">
            <div class="delimeter">cookies</div>
            <xsl:apply-templates select="cookie"/>
        </div>
    </xsl:template>

    <xsl:template match="cookie">
        <div><xsl:value-of select="@name"/>&#160;=&#160;<xsl:value-of select="."/>
        </div>
    </xsl:template>

    <xsl:template match="params">
        <div class="params">
            <div class="delimeter">params</div>
            <xsl:apply-templates select="param"/>
        </div>
    </xsl:template>

    <xsl:template match="param">
        <div>
            <xsl:value-of select="@name"/><xsl:text>&#160;=&#160;</xsl:text><xsl:value-of select="."/>
        </div>
    </xsl:template>


    <xsl:template match="log" mode="css">
        <style>
            body { margin: 0 10px; }
            body, pre{
                font-family:Arial;
            }
            pre{
                margin:0;
                white-space: pre-wrap;
            }
            .body{
                word-break: break-all;
            }
            .textentry{
                padding-left:20px;
                padding-right:20px;
                margin-bottom:4px;
                word-break: break-all;
            }
                .m-textentry__expandable{
                    padding-top:3px;
                    padding-bottom:3px;
                    background:#fffccf;
                }
                .m-textentry_title{
                    font-size:1.3em;
                    margin-bottom:.5em;
                }
                .textentry__head{
                }
                    .m-textentry__head_highlight{
                        font-weight:bold;
                    }
                    .textentry__head__expandtext{
                        border-bottom:1px dotted #666;
                    }
                .textentry__switcher{
                    height:1.3em;
                    overflow:hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                    cursor:pointer;
                }
            .headers{
            }
            .details{
                display:none;
                margin-bottom:15px;
            }
                .m-details_visible{
                    display:block;
                }

            .servicelink{
                color:#666;
                font-size:.8em;
            }
            .coloredxml__line{
                padding: 0px 0px 0px 20px;
            }
            .coloredxml__tag, .coloredxml__param{
                color: #9c0628;
            }
            .coloredxml__value{
            }
            .coloredxml__comment{
                color: #063;
                display: block;
                padding: 0px 0px 0px 30px;
                padding-top: 20px;
            }
            .time{
                display:inline-block;
                width:4em;
            }
            .error{
                color:red;
            }
            .ERROR{
                color:#c00;
            }
            .WARNING{
                color:#E80;
            }
            .INFO{
                color:#060;
            }
            .DEBUG{
                color:#00B;
            }
            .delimeter{
                margin-top:10px;
                font-size:.8em;
                color:#999;
            }
            .exception{
                margin-bottom:20px;
                color:#c00;
            }
            .iframe{
                width:100%;
                height:500px;
                background:#fff;
                border:1px solid #ccc;
                margin-top:5px;
                box-shadow:1px 1px 8px #aaacca;
                -moz-box-shadow:1px 1px 8px #aaacca;
                -webkit-box-shadow:1px 1px 8px #aaacca;
            }
            .debug-inherited{
                margin: 10px 0;
                padding: 10px;
                border: 1px solid #ccc;
                background: #fff;
            }
        </style>
    </xsl:template>

    <xsl:template match="log" mode="js">
        <script>
            function toggle(entry){
                var head = entry.querySelector('.textentry__head');
                if (head.className.indexOf('m-textentry__switcher_expand') != -1)
                    head.className = head.className.replace(/m-textentry__switcher_expand/, '');
                else{
                    head.className = head.className + ' m-textentry__switcher_expand';
                }
                var details = entry.querySelector('.details')
                if (details.className.indexOf('m-details_visible') != -1)
                    details.className = details.className.replace(/m-details_visible/, '');
                else{
                    details.className = details.className + ' m-details_visible';
                }
            }
            function doiframe(id, text){
                var iframe = window.document.createElement('iframe');
                iframe.className = 'iframe'
                var html = text
                    .replace(/&lt;/g, '<xsl:text disable-output-escaping="yes">&lt;</xsl:text>')
                    .replace(/&gt;/g, '<xsl:text disable-output-escaping="yes">&gt;</xsl:text>')
                    .replace(/&amp;/g, '<xsl:text disable-output-escaping="yes">&amp;</xsl:text>');
                window.document.getElementById(id).appendChild(iframe);
                var document = iframe.contentWindow.document;
                document.open();
                document.write(html);
                //document.close();
            }
        </script>
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
