<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:template match="doc">
<html><body>
<xsl:apply-templates select="ok" />
</body></html>
</xsl:template>

<xsl:template match="ok">
<h1>ok</h1>
</xsl:template>


</xsl:stylesheet>

