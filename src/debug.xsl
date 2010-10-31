<xsl:stylesheet version="1.0" id="style" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:template match="/debug">
    <html>
      <title>Status <xsl:value-of select="log/@code"/></title>
      <xsl:apply-templates select="." mode="css"/>
      <xsl:apply-templates select="." mode="js"/>
    </html>
    <body>
      <xsl:apply-templates select="log"/>
    </body>
  </xsl:template>
  
  <xsl:template match="log">
    <div class="textentry m-textentry_title">
      requestid: <xsl:value-of select="@request-id"/>,
      status: <xsl:value-of select="@code"/>
    </div>
    <xsl:apply-templates select="entry"/>
  </xsl:template>
  
  <xsl:template match="entry[contains(@msg, 'finish group') and /debug/@mode != 'full']"/>
  
  <xsl:template match="entry">
    <div class="textentry">
      <div class="textentry__head">
        <span  title="{@msg}"><xsl:value-of select="@msg"/></span>
      </div>
    </div>
  </xsl:template>
  
  <xsl:template match="entry[response]">
    <xsl:variable name="status">
      <xsl:if test="response/code != 200">error</xsl:if>
    </xsl:variable>
    <div class="textentry" onclick="toggle(this)">
      <div class="textentry__head textentry__switcher {$status}">
        <span  title="{@msg}">
          <span class="time">
            <xsl:value-of select="response/request_time"/>
            <xsl:text>ms </xsl:text>
          </span>
          <xsl:value-of select="response/code"/>
          <xsl:text> </xsl:text>
          <xsl:value-of select="request/method"/>
          <xsl:text> </xsl:text>
          <xsl:value-of select="request/url"/>
        </span>
      </div>
      <div class="details">
        <xsl:apply-templates select="request"/>
        <div>---------------------------</div>
        <xsl:apply-templates select="response"/>
      </div>
    </div>
  </xsl:template>

  <xsl:template match="request">
    <div>
      <a class="servicelink" href="{url}" target="_blank">
        <xsl:value-of select="url"/>
      </a>
    </div>
    <xsl:apply-templates select="headers"/>
    <xsl:apply-templates select="params"/>
    <xsl:apply-templates select="body"/>
  </xsl:template>
  
  <xsl:template match="response">
    <xsl:apply-templates select="error"/>
    <xsl:apply-templates select="headers"/>
    <xsl:apply-templates select="body[node()]" mode="xml"/>
    <xsl:apply-templates select="body[not(node())]"/>
  </xsl:template>

  <xsl:template match="body">
    <xsl:value-of select="."/>
  </xsl:template>

  <xsl:template match="error[text() = 'None']"/>

  <xsl:template match="error">
    <div class="error">
      <xsl:value-of select="."/>
    </div>
  </xsl:template>

  <xsl:template match="body" mode="xml">
    <div class="coloredxml">
      <xsl:apply-templates select="node()" mode="color-xml"/>
    </div>
  </xsl:template>
  
  <xsl:template match="headers">
    <div class="headers">
      <xsl:apply-templates select="header"/>
    </div>
  </xsl:template>
  
  <xsl:template match="header">
    <div><xsl:value-of select="@name"/>: &#160;<xsl:value-of select="."/></div>
  </xsl:template>

  <xsl:template match="params">
    <div class="params">
      <xsl:apply-templates select="param"/>
    </div>
  </xsl:template>
  
  <xsl:template match="param">
    <div><xsl:value-of select="@name"/>=<xsl:value-of select="."/></div>
  </xsl:template>
  

  <xsl:template match="debug" mode="css">
    <style>
      body{
        font-family:Arial;
      }
      .textentry{
        margin-left:20px;
        margin-bottom:4px;
      }
        .m-textentry_title{
          font-size:1.3em;
          margin-bottom:.5em;
        }
        .textentry__head{
          height:1.3em;
          overflow:hidden;
        }
        .textentry__switcher{
          cursor:pointer;
        }
          .textentry__switcher:before{
            position:absolute;
            margin-top:2px;
            margin-left:-16px;
            content: "+"
          }
            .m-textentry__switcher_expand:before{
              margin-top:0px;
              margin-left:-15px;
              content: "-"
            }
      .headers{
        margin:10px 0;
        font-size:.8em;
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
     .coloredxml{
       margin-left:-20px;
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
    </style>
  </xsl:template>
  
  <xsl:template match="debug" mode="js">
    <script>
      function toggle(entry){
        entry.querySelector('.textentry__head')
          .classList.toggle('m-textentry__switcher_expand');
        entry.querySelector('.details')
          .classList.toggle('m-details_visible');
      }
    </script>
  </xsl:template>
  
  <xsl:template match="*" mode="color-xml">
    <div class="coloredxml__line">
      <xsl:text>&lt;</xsl:text>
      <span class="coloredxml__tag"><xsl:value-of select="name()" /></span>
      
      <xsl:for-each select="@*">
        <xsl:text> </xsl:text>
        <span class="coloredxml__param"><xsl:value-of select="name()" /></span>
        <xsl:text>="</xsl:text>
        <span class="coloredxml__value">
          <xsl:if test="not(string-length(.))"><xsl:text> </xsl:text></xsl:if>
          <xsl:value-of select="."/>
        </span>
        <xsl:text>"</xsl:text>
      </xsl:for-each>
      
      <xsl:choose>
        <xsl:when test="node()">
          <xsl:text>&gt;</xsl:text>
          <xsl:apply-templates select="node()" mode="color-xml" />
          <xsl:text>&lt;/</xsl:text>
          <span class="coloredxml__tag"><xsl:value-of select="name()" /></span>
          <xsl:text>&gt;</xsl:text>
        </xsl:when>
        <xsl:otherwise>
          <xsl:text>/&gt;</xsl:text>
        </xsl:otherwise>
      </xsl:choose>
    </div>
  </xsl:template>
  
  <xsl:template match="text()" mode="color-xml">
    <span class="coloredxml__value"><xsl:value-of select="."/></span>
  </xsl:template>
  
  <xsl:template match="comment()" mode="color-xml">
    <span class="coloredxml__comment">
      &lt;!--<xsl:value-of select="." />--&gt;
    </span>
  </xsl:template>
</xsl:stylesheet>