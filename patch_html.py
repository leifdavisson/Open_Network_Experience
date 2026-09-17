import re

with open('server/templates/dashboard.html', 'r') as f:
    content = f.read()

replacement = """                        <!-- Control 4: Chrome Extension Packager -->
                        <div style="background: var(--bg-input); padding: 14px; border-radius: 8px; border: 1px solid var(--border);">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <strong style="color: var(--text); font-size: 13px;">🏗️ Workspace Packager</strong>
                                <span class="badge" style="background: rgba(139, 92, 246, 0.2); color: #c4b5fd; font-size: 11px;">Native</span>
                            </div>
                            <div style="font-size: 11px; color: var(--text-muted); margin: 6px 0 10px 0;">
                                Instantly compile and sign the extension for Google Admin deployment without the Chrome Web Store.
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 8px;">
                                <button class="btn btn-sm" id="btn-rebuild-ext" onclick="rebuildExtension()" style="background: #8b5cf6; color: white; padding: 6px 10px; font-size: 11px; font-weight: bold;">🚀 Rebuild & Publish (.crx)</button>
                                <input type="text" id="ext-custom-url" readonly value="/chromebook/update.xml" style="width: 100%; padding: 5px 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg); color: var(--text); font-size: 11px;" title="Paste into Workspace Admin Custom URL" onclick="this.select();">
                            </div>
                        </div>
                    </div>"""

# Replace the closing div of the grid
content = content.replace('                            </div>\n                        </div>\n\n                    </div>\n\n                    <!-- Active Fleet Data Table -->', replacement + '\n\n                    <!-- Active Fleet Data Table -->')

with open('server/templates/dashboard.html', 'w') as f:
    f.write(content)
