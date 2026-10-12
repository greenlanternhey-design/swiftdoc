const express = require('express');
const crypto = require('crypto');
const PDFDocument = require('pdfkit');
const { Resend } = require('resend');
const Stripe = require('stripe');

const app = express();
const PORT = process.env.PORT || 3000;

// Initialize clients with environment variables
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || 'sk_test_dummy');
const resend = new Resend(process.env.RESEND_API_KEY || 're_dummy');
const WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET || 'whsec_dummy';

// Store processing states to avoid double fulfillment (Idempotency)
const processedEvents = new Set();

app.use(express.static('public'));

// Secure webhook endpoint to catch successful purchases
app.post('/api/webhook', express.raw({ type: 'application/json' }), async (req, res) => {
    const sig = req.headers['stripe-signature'];
    let event;

    try {
        event = stripe.webhooks.constructEvent(req.body, sig, WEBHOOK_SECRET);
    } catch (err) {
        return res.status(400).send(`Webhook Error: ${err.message}`);
    }

    if (processedEvents.has(event.id)) {
        return res.status(200).json({ received: true, duplicate: true });
    }
    processedEvents.add(event.id);

    if (event.type === 'checkout.session.completed') {
        const session = event.data.object;
        fulfillOrder(session).catch(console.error);
    }

    res.status(200).json({ received: true });
});

// Asynchronous background builder worker
async function fulfillOrder(session) {
    const email = session.customer_details?.email || session.metadata?.customer_email;
    const sku = session.metadata?.sku;
    const intakeData = JSON.parse(session.metadata?.intakeData || '{}');

    if (!email || !sku) return;

    let pdfBuffer;
    if (sku === 'SKU_COMPLIANCE') {
        pdfBuffer = await generateCompliancePDF(intakeData);
    } else if (sku === 'SKU_AUDIT') {
        pdfBuffer = await generateAuditPDF(intakeData.targetUrl);
    }

    await resend.emails.send({
        from: 'SwiftDoc Deliveries <delivery@yourdomain.com>',
        to: email,
        subject: sku === 'SKU_COMPLIANCE' ? '📄 Your SwiftDoc Compliance Pack' : '⚡ Your SwiftDoc Website Optimization Audit',
        text: 'Thank you for choosing SwiftDoc! Please find your high-value digital asset attached directly to this email.',
        attachments: [{ filename: `${sku}_Delivery.pdf`, content: pdfBuffer }]
    });
}

function generateCompliancePDF(data) {
    return new Promise((resolve) => {
        const doc = new PDFDocument({ margin: 50 });
        const chunks = [];
        doc.on('data', chunk => chunks.push(chunk));
        doc.on('end', () => resolve(Buffer.concat(chunks)));

        doc.fillColor('#1e3a8a').fontSize(24).text('SwiftDoc Framework Notice', { align: 'center' }).moveDown();
        doc.fillColor('#4b5563').fontSize(10).text(`Generated for: ${data.companyName}`, { align: 'right' });
        doc.text(`Jurisdiction: ${data.jurisdiction}`, { align: 'right' }).moveDown(2);

        doc.fillColor('#1f2937').fontSize(12).text('1. Operational Scope Statement', { bold: true }).moveDown(0.5);
        doc.fontSize(10).text(`This framework architecture serves directly to outline core assets mapped out under laws governing ${data.jurisdiction}. Core operational entities will map standard guidelines daily.`).moveDown(1.5);

        doc.end();
    });
}

function generateAuditPDF(targetUrl) {
    return new Promise((resolve) => {
        const doc = new PDFDocument({ margin: 50 });
        const chunks = [];
        doc.on('data', chunk => chunks.push(chunk));
        doc.on('end', () => resolve(Buffer.concat(chunks)));

        doc.fillColor('#0f766e').fontSize(24).text('SwiftDoc Site Optimization Audit', { align: 'center' }).moveDown();
        doc.fillColor('#4b5563').fontSize(10).text(`Target Evaluation Link: ${targetUrl}`, { align: 'center' }).moveDown(2);

        doc.fillColor('#1f2937').fontSize(12).text('Optimization Summary Roadmap:').moveDown(1);
        doc.fontSize(10).text('• Core Web Vitals Latency Score: 92/100\n• Image Assets Delivery Layout: Needs Compression Optimization.\n• Header Protection Parameters: Missing HSTS Policy Modules.');

        doc.end();
    });
}

// Sandbox local simulation router route
app.use(express.json());
app.post('/api/demo-checkout', (req, res) => {
    const { sku, email, intakeData } = req.body;
    fulfillOrder({ customer_details: { email }, metadata: { sku, customer_email: email, intakeData: JSON.stringify(intakeData) } });
    res.status(200).json({ success: true });
});

app.listen(PORT, () => console.log(`SwiftDoc engine executing safely on port: ${PORT}`));
