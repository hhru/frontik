<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:template name="debug-js">
        <script><![CDATA[
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

            function select(entry) {
                if (document.body.createTextRange) {
                    var range = document.body.createTextRange();
                    range.moveToElementText(entry.querySelector('.details'));
                    range.select();
                } else if (window.getSelection) {
                    var selection = window.getSelection();
                    var range = document.createRange();
                    range.selectNode(entry.querySelector('.details'));
                    selection.removeAllRanges();
                    selection.addRange(range);
                }
            }

            document.addEventListener("DOMContentLoaded", function(event) {
                var sql = document.getElementsByClassName('language-sql highlighted-code');
                Array.prototype.forEach.call(sql, function(el) {
                    el.innerHTML = vkbeautify.sql(el.textContent);
                });

                var xml = document.getElementsByClassName('language-xml highlighted-code');
                Array.prototype.forEach.call(xml, function(el) {
                    el.innerHTML = vkbeautify.xml(el.textContent).replace(/</g, '&lt;');
                });

                var json = document.getElementsByClassName('language-js highlighted-code');
                Array.prototype.forEach.call(json, function(el) {
                    el.innerHTML = vkbeautify.json(el.textContent).replace(/</g, '&lt;');
                });

                Prism.highlightAll();

                var switchers = document.getElementsByClassName('entry__switcher');
                Array.prototype.forEach.call(switchers, function(switcher) {
                    switcher.addEventListener('click', function(e) {
                        e.preventDefault();
                        var details = this.querySelector('.details');
                        if (details.className.indexOf('m-details_visible') != -1) {
                            details.className = details.className.replace(/\bm-details_visible\b/, '');
                            this.className = this.className.replace(/\bentry_expanded\b/, 'entry_expandable')
                        } else {
                            details.className = details.className + ' m-details_visible';
                            this.className = this.className.replace(/\bentry_expandable\b/, 'entry_expanded')
                        }
                        console.log(this.className, this)
                        return false;
                    }.bind(switcher.parentNode), false);
                });
            });
        ]]></script>
    </xsl:template>

</xsl:stylesheet>
