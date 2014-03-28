<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:template name="debug-js">
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

</xsl:stylesheet>
