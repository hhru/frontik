<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:template match="doc">
<html><body>
<xsl:apply-templates select="id" />
</body></html>
</xsl:template>

<xsl:template match="id">
<h1><xsl:value-of select="@value"/></h1>
</xsl:template>


</xsl:stylesheet>

