const express = require('express');
const path = require('path');
const app = express();

app.use(express.json());

// Serve the frontend files from the public folder automatically
app.use(express.static(path.join(__dirname, 'public')));

// Secure route to handle downloading your new ZIP package safely
app.get('/download-package', (req, res) => {
    const fileLocation = path.join(__dirname, 'public', 'clausecheck.zip');
    res.download(fileLocation, 'clausecheck.zip', (error) => {
        if (error) {
            console.error("Download failed:", error);
            if (!res.headersSent) {
                res.status(500).send("Package download currently unavailable.");
            }
        }
    });
});

// Fallback to send clients to the main index.html dashboard interface
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Export the application configuration interface for Vercel Serverless environment
module.exports = app;
