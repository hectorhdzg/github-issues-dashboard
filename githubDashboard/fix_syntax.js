const fs = require('fs');

// Read the file
const content = fs.readFileSync('static/js/spa.js', 'utf8');
const lines = content.split('\n');

// Find the problematic section and remove the incomplete loadDashboardData method
const newLines = [];
let skipMode = false;
let foundFirstMethod = false;

for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    // Start skipping at first incomplete loadDashboardData
    if (line.trim() === 'async loadDashboardData() {' && !foundFirstMethod) {
        skipMode = true;
        foundFirstMethod = true;
        continue;
    }
    
    // Stop skipping after we see the end of the incomplete method
    if (skipMode && line.trim() === '}' && lines[i+1] && lines[i+1].trim() === '') {
        skipMode = false;
        continue;
    }
    
    // Skip lines in skip mode
    if (skipMode) {
        continue;
    }
    
    newLines.push(line);
}

// Write the cleaned file
fs.writeFileSync('static/js/spa.js', newLines.join('\n'));
console.log('Fixed syntax error by removing incomplete loadDashboardData method');