<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:template name="debug-css">
        <style>
            body { margin: 0 10px; }
            body, pre {
                font-family: sans-serif;
            }
            pre {
                margin: 0;
                white-space: pre-wrap;
            }
            code {
                max-height: 500px;
                overflow-y: auto;
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
                white-space: nowrap;
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
                        white-space: pre-wrap;
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
                padding-bottom: 8px;
                position: relative;
            }
                .m-details_visible,
                .details-expander:checked + .details {
                    display:block;
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
                margin-bottom: 2px;
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

            .copy-as-curl-link {
                display: block;
                text-decoration: underline;
                cursor: pointer;
            }

            .copy-as-curl {
                max-width: 100%;
                margin: 10px 0;
                padding: 4px;
                background: #fff;
                font-family: monospace;
            }
        </style>
    </xsl:template>

</xsl:stylesheet>
