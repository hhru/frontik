<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:template match="doc">
    <html>
        <xsl:apply-templates select="node" />
    </html>
</xsl:template>

<xsl:template match="node">
    <h1>{{header}}</h1>{{content}}
</xsl:template>

</xsl:stylesheet>
