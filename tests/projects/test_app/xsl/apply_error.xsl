<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:template match="doc">
<html><body>
    <xsl:call-template name="q"/>
    <xsl:value-of select="$nonexistingvar" />
</body></html>
</xsl:template>

</xsl:stylesheet>

