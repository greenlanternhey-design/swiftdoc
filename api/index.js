const express = require('express');
const path = require('path');
const app = express();

app.use(express.json());

// 1. Core checkout route mapping
app.post('/api/demo-checkout', (req, res) => {
    const { sku, email, intakeData } = req.body;
    res.status(200).json({ 
        success: true, 
        message: "File generation pipeline active." 
    });
});

// 2. Secure file package download route
app.get('/api/download-package', (req, res) => {
    const fileLocation = path.join(process.cwd(), 'public', 'clausecheck.zip');
    
    res.download(fileLocation, 'clausecheck.zip', (error) => {
        if (error) {
            console.error("Package download stream failed:", error);
            if (!res.headersSent) {
                res.status(500).send("Package asset momentarily offline.");
            }
        }
    });
});

module.exports = app;
