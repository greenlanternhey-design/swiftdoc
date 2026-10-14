import React from 'react';

export default function EnterpriseDownload() {
  // Replace this with your exact GitHub Release direct download asset URL
  const gitHubReleaseUrl = "https://github.com";

  return (
    <div style={{
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      padding: '32px',
      border: '1px solid #e1e4e8',
      borderRadius: '6px',
      maxWidth: '460px',
      backgroundColor: '#fafbfc'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '12px' }}>
        {/* GitHub Inspired Octicon Branding */}
        <span style={{ fontSize: '24px', marginRight: '10px' }}>📦</span>
        <h3 style={{ margin: 0, color: '#24292e', fontSize: '16px', fontWeight: 600 }}>
          SwiftDoc ClauseCheck Runtime
        </h3>
      </div>
      
      <p style={{ margin: '0 0 24px 0', color: '#586069', fontSize: '14px', lineHeight: '1.5' }}>
        Enterprise Edition Annual License. Securely download the complete verified offline runtime system and structural optimization templates.
      </p>
      
      <a 
        href={gitHubReleaseUrl}
        style={{
          display: 'inline-block',
          backgroundColor: '#2ea44f',
          color: '#ffffff',
          padding: '8px 16px',
          textDecoration: 'none',
          borderRadius: '6px',
          fontWeight: '500',
          fontSize: '14px',
          boxShadow: '0 1px 0 rgba(27,31,35,0.1)'
        }}
        onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#2c974b'}
        onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#2ea44f'}
      >
        Download clausecheck.zip
      </a>
    </div>
  );
}
