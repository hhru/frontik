<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:template name="debug-css">
        <style>
            body { margin: 0; }
            body, pre {
                font-family: sans-serif;
            }
            pre {
                margin: 0;
                white-space: pre-wrap;
            }
            code {
                overflow-y: auto;
            }
            .body {
                word-break: break-all;
                max-height: 500px;
            }

            .timeline {
                position: absolute;
                height: 100%;
                border-left: 1px dashed green;
                border-right: 1px dashed green;
                box-sizing: border-box;
                opacity: 0.2;
            }
                .timeline_debug {
                    border-left: none;
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
                    display: block;
                    width: 0;
                    height: 1.4em;
                    background-color: #94b24d;
                    border-left: 1px solid green;
                    border-right: 1px solid green;
                    box-sizing: border-box;
                    opacity: 0.5;
                }
                    .timebar__head_error {
                        background-color: red;
                    }
            .timebar-details {
                left: 0;
                top: 0;
                height: 100%;
                width: 100%;
                margin-left: -20px;
                margin-right: -20px;
                white-space: nowrap;
            }

            .entry {
                margin-bottom: 4px;
                word-break: break-all;
                position: relative;
            }
                .entry_expandable, .entry_expanded {
                    background: #fffccf;
                }
                    .entry.entry_expandable:before, .entry.entry_expanded:before {
                        float: left;
                        position: absolute;
                        width: 20px;
                        padding: 3px 0;
                        text-align: center;
                        font-size: 0.8em;
                    }
                    .entry.entry_expandable:before {
                        content: "▹";
                    }
                    .entry.entry_expanded:before {
                        content: "▿";
                    }
                .entry_title {
                    font-size: 1.2em;
                    margin: 0.5em 0;
                    margin-left: 20px;
                }
                .entry__head {
                    display: block;
                }
                    .entry__head_highlight {
                        font-weight: bold;
                    }
                    .entry__head__expandtext {
                        display: inline-block;
                        position: relative;
                        padding: 3px 0;
                        padding-left: 20px;
                        vertical-align: bottom;
                    }
                    .entry__head__level {
                        font-size: 14px;
                        font-family: monospace;
                    }
                    .entry__head__message {
                        display: inline-block;
                        padding: 2px 0;
                        padding-left: 20px;
                        white-space: pre-wrap;
                    }
                .entry__switcher {
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                    cursor: pointer;
                }

            .headers{
            }

            .line {
                height: 12px;
                margin-bottom: 12px;
                text-align: center;
                border-bottom: 1px solid #eee;
            }
                .line__bar {
                    position: absolute;
                    height: 0;
                    margin-top: 10px;
                    border-bottom: 4px solid #94b24d;
                    opacity: 0.5;
                }
                    .line__bar_error {
                        border-color: #c00;
                    }
                    .line__bar_warning {
                        border-color: #E80;
                    }
                    .line__bar_info {
                        border-color: #060;
                    }
                    .line__bar_debug {
                        border-color: #00B;
                    }
                .line__label {
                    position: relative;
                    padding: 0 3px;
                    font-size: 0.9em;
                    line-height: 24px;
                    background: white;
                    border-radius: 2px;
                }

            .details-expander {
                display: none;
            }
            .details {
                display: none;
                padding-bottom: 8px;
                padding-left: 20px;
                padding-right: 20px;
                position: relative;
            }
                .details_debug {
                    border-bottom: 1px solid #ccc;
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
                padding-left: 20px;
                color: #c00;
            }

            .iframe {
                width: 100%;
                height: 500px;
                margin-top: 5px;
                background: #fff;
                border: 1px solid #ccc;
                box-sizing: border-box;
            }

            .debug-inherited {
                position: relative;
                margin: 10px 0;
                margin-left: -20px;
                margin-right: -20px;
                border-top: 1px solid #ccc;
                border-bottom: 1px solid #ccc;
                background: #fff;
            }
                .debug-inheritance {
                    left: 0;
                    width: 3px;
                    height: 100%;
                    margin-top: -24px;
                    padding-bottom: 24px;
                    position: absolute;
                    background: orange;
                    z-index: 1;
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
