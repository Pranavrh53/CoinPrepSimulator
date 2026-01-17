"""
Advanced Risk Assessment Routes for Flask App
These routes handle comprehensive multi-test risk assessment with AI analysis
"""

from flask import request, jsonify, render_template, session, redirect, url_for
from datetime import datetime
import json
from risk_assessment_data import (
    FINANCIAL_CAPACITY_TEST,
    INVESTMENT_KNOWLEDGE_TEST,
    PSYCHOLOGICAL_TOLERANCE_TEST,
    GOALS_TIMELINE_TEST,
    RISK_CATEGORIES,
    get_ai_analysis_prompt
)

def calculate_test_score(test_data, responses):
    """Calculate percentage score for a single test"""
    total_possible = sum(max(opt['points'] for opt in q['options']) for q in test_data['questions'])
    total_earned = sum(responses.get(q['id'], 0) for q in test_data['questions'])
    return round((total_earned / total_possible) * 100, 2)

def get_risk_category(weighted_score):
    """Get risk category based on weighted average score"""
    for category in RISK_CATEGORIES:
        if category['range'][0] <= weighted_score < category['range'][1]:
            return category
    return RISK_CATEGORIES[-1]  # Return most aggressive if > max

def get_db_connection():
    """Get database connection - should be imported from main app"""
    import mysql.connector
    db_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'Pranavrh123$',
        'database': 'crypto_tracker'
    }
    return mysql.connector.connect(**db_config)

def generate_ai_analysis(scores, user_data):
    """Generate AI-powered analysis of user's risk profile"""
    # Simple rule-based AI analysis (can be replaced with actual AI API)
    analysis = {
        'summary': '',
        'strengths': [],
        'concerns': [],
        'recommendations': [],
        'asset_allocation': {},
        'crypto_advice': '',
        'action_steps': [],
        'risk_management': []
    }
    
    # Summary
    category = get_risk_category(scores['total'])
    analysis['summary'] = f"Your comprehensive risk assessment indicates a **{category['level']}** risk profile with an overall score of {scores['total']}%. {category['description']}"
    
    # Analyze each dimension
    # Financial Capacity Analysis
    if scores['financial'] >= 70:
        analysis['strengths'].append("Strong financial capacity with good income stability and emergency reserves")
    elif scores['financial'] >= 50:
        analysis['strengths'].append("Adequate financial capacity to support moderate risk-taking")
    else:
        analysis['concerns'].append("Limited financial capacity - focus on building emergency fund before aggressive investing")
    
    # Knowledge Analysis
    if scores['knowledge'] >= 70:
        analysis['strengths'].append("Solid investment knowledge and experience base")
    elif scores['knowledge'] >= 50:
        analysis['strengths'].append("Good foundational investment knowledge")
    else:
        analysis['concerns'].append("Limited investment knowledge - consider educational resources before complex strategies")
    
    # Psychological Tolerance Analysis
    if scores['psychological'] >= 70:
        analysis['strengths'].append("Strong emotional resilience to market volatility")
    elif scores['psychological'] >= 50:
        analysis['strengths'].append("Moderate psychological comfort with market fluctuations")
    else:
        analysis['concerns'].append("Low psychological tolerance for volatility - stick to stable investments")
    
    # Goals & Timeline Analysis
    if scores['goals'] >= 70:
        analysis['strengths'].append("Long time horizon allowing for growth-oriented strategies")
    elif scores['goals'] >= 50:
        analysis['strengths'].append("Moderate timeline suitable for balanced approach")
    else:
        analysis['concerns'].append("Short time horizon - prioritize capital preservation")
    
    # Check for mismatches
    capacity_vs_tolerance = abs(scores['financial'] - scores['psychological'])
    if capacity_vs_tolerance > 30:
        if scores['financial'] > scores['psychological']:
            analysis['concerns'].append("⚠️ MISMATCH: You have financial capacity but low psychological tolerance - start conservatively")
        else:
            analysis['concerns'].append("⚠️ MISMATCH: High risk appetite but limited financial capacity - be cautious")
    
    knowledge_vs_tolerance = abs(scores['knowledge'] - scores['psychological'])
    if knowledge_vs_tolerance > 30:
        if scores['knowledge'] < scores['psychological']:
            analysis['concerns'].append("⚠️ CAUTION: Risk appetite exceeds investment knowledge - educate yourself before aggressive moves")
    
    # Recommendations based on profile
    if scores['total'] < 30:
        analysis['recommendations'] = [
            "Focus on capital preservation with high-quality bonds and savings accounts",
            "Build emergency fund covering 6-12 months of expenses",
            "Consider low-cost index funds for equity exposure (10-20% max)",
            "Avoid speculative assets and complex derivatives",
            "Review portfolio quarterly but avoid frequent trading"
        ]
    elif scores['total'] < 45:
        analysis['recommendations'] = [
            "Maintain 50-60% in bonds and stable income assets",
            "Allocate 30-40% to diversified equity funds",
            "Consider dividend-paying stocks for income",
            "Keep 10% in cash for opportunities and emergencies",
            "Rebalance annually to maintain target allocation"
        ]
    elif scores['total'] < 55:
        analysis['recommendations'] = [
            "Balanced 50-50 or 60-40 stock-bond allocation",
            "Diversify across sectors, market caps, and geographies",
            "Include 5-10% alternative investments for diversification",
            "Consider tax-loss harvesting strategies",
            "Rebalance semi-annually or when allocations drift 5%+"
        ]
    elif scores['total'] < 65:
        analysis['recommendations'] = [
            "Growth-focused 60-70% equity allocation",
            "Include growth stocks, small-caps, and emerging markets",
            "Limit bonds to 20-30% for stability",
            "Consider sector-specific ETFs for targeted exposure",
            "Maintain discipline during market corrections"
        ]
    else:
        analysis['recommendations'] = [
            "Aggressive 75-85% equity allocation for maximum growth",
            "Include high-growth stocks, small-caps, and alternatives",
            "Consider sector rotation strategies",
            "Include international and emerging markets (20-30%)",
            "Prepare for 30-50% portfolio swings during market cycles"
        ]
    
    # Asset allocation
    analysis['asset_allocation'] = category['allocation']
    
    # Crypto-specific advice
    crypto_pct = category['crypto_allocation']
    if scores['total'] < 30:
        analysis['crypto_advice'] = f"Cryptocurrency allocation: {crypto_pct}. Limit to well-established coins (BTC, ETH) only. Treat as speculative <2% of portfolio."
    elif scores['total'] < 45:
        analysis['crypto_advice'] = f"Cryptocurrency allocation: {crypto_pct}. Focus on top 10 cryptocurrencies by market cap. Consider dollar-cost averaging."
    elif scores['total'] < 55:
        analysis['crypto_advice'] = f"Cryptocurrency allocation: {crypto_pct}. Diversify across 5-10 established cryptocurrencies. Include both large-cap and mid-cap coins."
    elif scores['total'] < 65:
        analysis['crypto_advice'] = f"Cryptocurrency allocation: {crypto_pct}. Can explore beyond top 20 coins. Consider DeFi and blockchain projects with strong fundamentals."
    else:
        analysis['crypto_advice'] = f"Cryptocurrency allocation: {crypto_pct}. Can include small-cap and emerging projects. Consider staking and DeFi strategies. Stay informed on regulatory changes."
    
    # Action steps
    analysis['action_steps'] = [
        f"Review current portfolio allocation against recommended {category['level']} profile",
        f"Ensure emergency fund is adequate ({user_data.get('emergency_months', '3-6')} months expenses)",
        "Set up automatic rebalancing alerts when allocations drift >5%",
        "Review and adjust risk tolerance annually or after major life changes",
        "Track performance against appropriate benchmarks for your allocation"
    ]
    
    # Risk management strategies
    if scores['total'] < 40:
        analysis['risk_management'] = [
            "Use stop-loss orders at 5-10% below purchase price",
            "Avoid margin and leverage entirely",
            "Diversify across at least 15-20 holdings",
            "Keep 20-30% in cash and cash equivalents",
            "Review portfolio monthly but trade infrequently"
        ]
    elif scores['total'] < 60:
        analysis['risk_management'] = [
            "Use stop-loss orders at 10-15% below purchase price",
            "Limit single position size to 5-7% of portfolio",
            "Diversify across 10-15 holdings",
            "Maintain 5-10% cash position",
            "Review quarterly and rebalance as needed"
        ]
    else:
        analysis['risk_management'] = [
            "Use trailing stops on individual positions",
            "Can concentrate in 6-10 high-conviction positions",
            "Accept wider position sizing (up to 10% each)",
            "Minimal cash drag (0-5%) for maximum market exposure",
            "Active monitoring with quarterly deep reviews"
        ]
    
    return analysis

# Routes to be added to main Flask app

def risk_assessment_home():
    """Main risk assessment page showing all available tests"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    
    # Get user's existing assessment if any
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM risk_assessments 
        WHERE user_id = %s 
        ORDER BY completed_at DESC LIMIT 1
    """, (session['user_id'],))
    last_assessment = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return render_template('combined.html', 
                          section='risk_assessment_home',
                          last_assessment=last_assessment,
                          user=session)

def take_assessment():
    """Combined page showing all tests"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    
    tests = {
        'financial': FINANCIAL_CAPACITY_TEST,
        'knowledge': INVESTMENT_KNOWLEDGE_TEST,
        'psychological': PSYCHOLOGICAL_TOLERANCE_TEST,
        'goals': GOALS_TIMELINE_TEST
    }
    
    return render_template('combined.html',
                          section='risk_assessment_test',
                          tests=tests,
                          user=session)

def submit_assessment():
    """Process submitted assessment and generate report"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Not authenticated'}), 401
    
    if request.method != 'POST':
        return jsonify({'error': 'Method not allowed'}), 405
    
    try:
        responses = request.json.get('responses', {})
        
        # Calculate scores for each test
        financial_score = calculate_test_score(FINANCIAL_CAPACITY_TEST, responses)
        knowledge_score = calculate_test_score(INVESTMENT_KNOWLEDGE_TEST, responses)
        psychological_score = calculate_test_score(PSYCHOLOGICAL_TOLERANCE_TEST, responses)
        goals_score = calculate_test_score(GOALS_TIMELINE_TEST, responses)
        
        # Calculate weighted average
        weighted_score = round(
            financial_score * FINANCIAL_CAPACITY_TEST['weight'] +
            knowledge_score * INVESTMENT_KNOWLEDGE_TEST['weight'] +
            psychological_score * PSYCHOLOGICAL_TOLERANCE_TEST['weight'] +
            goals_score * GOALS_TIMELINE_TEST['weight'],
            2
        )
        
        # Get risk category
        category = get_risk_category(weighted_score)
        
        # Prepare scores dict
        scores = {
            'financial': financial_score,
            'knowledge': knowledge_score,
            'psychological': psychological_score,
            'goals': goals_score,
            'total': weighted_score,
            'category': category['level']
        }
        
        # Extract user data for AI analysis
        user_data = {
            'age': responses.get('fc1', 'Not provided'),
            'experience': responses.get('ik1', 'Not provided'),
            'goal': responses.get('gt1', 'Not provided'),
            'timeline': responses.get('gt2', 'Not provided'),
            'emergency_months': '3-6'  # Default
        }
        
        # Generate AI analysis
        ai_analysis = generate_ai_analysis(scores, user_data)
        
        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO risk_assessments (
                user_id, financial_score, knowledge_score, 
                psychological_score, goals_score, total_score,
                risk_category, responses, ai_analysis, completed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session['user_id'],
            financial_score,
            knowledge_score,
            psychological_score,
            goals_score,
            weighted_score,
            category['level'],
            json.dumps(responses),
            json.dumps(ai_analysis),
            datetime.now()
        ))
        
        assessment_id = cursor.lastrowid
        
        # Update user's risk level
        cursor.execute("""
            UPDATE users 
            SET risk_level = %s, risk_score = %s
            WHERE id = %s
        """, (category['level'], weighted_score, session['user_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'assessment_id': assessment_id,
            'scores': scores,
            'category': category,
            'analysis': ai_analysis
        })
        
    except Exception as e:
        print(f"Error submitting assessment: {e}")
        return jsonify({'error': str(e)}), 500

def view_report(assessment_id):
    """View detailed assessment report"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM risk_assessments 
        WHERE id = %s AND user_id = %s
    """, (assessment_id, session['user_id']))
    
    assessment = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not assessment:
        return "Assessment not found", 404
    
    # Parse JSON fields
    assessment['ai_analysis'] = json.loads(assessment['ai_analysis'])
    assessment['responses'] = json.loads(assessment['responses'])
    
    # Get category details
    category = get_risk_category(assessment['total_score'])
    
    return render_template('combined.html',
                          section='risk_assessment_report',
                          assessment=assessment,
                          category=category,
                          user=session)

def download_report(assessment_id):
    """Generate and download PDF report"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from io import BytesIO
        from flask import send_file
        
        # Get assessment data
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT ra.*, u.username, u.email 
            FROM risk_assessments ra
            JOIN users u ON ra.user_id = u.id
            WHERE ra.id = %s AND ra.user_id = %s
        """, (assessment_id, session['user_id']))
        assessment = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not assessment:
            return jsonify({'error': 'Assessment not found'}), 404
        
        # Parse JSON
        ai_analysis = json.loads(assessment['ai_analysis'])
        category = get_risk_category(assessment['total_score'])
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2563eb'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # Add title
        story.append(Paragraph("Comprehensive Risk Assessment Report", title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # User info
        story.append(Paragraph(f"<b>Name:</b> {assessment['username']}", styles['Normal']))
        story.append(Paragraph(f"<b>Email:</b> {assessment['email']}", styles['Normal']))
        story.append(Paragraph(f"<b>Date:</b> {assessment['completed_at'].strftime('%B %d, %Y')}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Scores section
        story.append(Paragraph("<b>Assessment Scores</b>", styles['Heading2']))
        scores_data = [
            ['Component', 'Score', 'Weight'],
            ['Financial Capacity', f"{assessment['financial_score']}%", '25%'],
            ['Investment Knowledge', f"{assessment['knowledge_score']}%", '20%'],
            ['Psychological Tolerance', f"{assessment['psychological_score']}%", '30%'],
            ['Goals & Timeline', f"{assessment['goals_score']}%", '25%'],
            ['', '', ''],
            ['Overall Risk Score', f"{assessment['total_score']}%", '100%']
        ]
        
        scores_table = Table(scores_data, colWidths=[2.5*inch, 1.5*inch, 1*inch])
        scores_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e0e7ff')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(scores_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Risk category
        story.append(Paragraph(f"<b>Risk Category:</b> {category['level']}", styles['Heading2']))
        story.append(Paragraph(category['description'], styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # AI Analysis Summary
        story.append(Paragraph("<b>Profile Summary</b>", styles['Heading2']))
        story.append(Paragraph(ai_analysis['summary'], styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Strengths
        if ai_analysis['strengths']:
            story.append(Paragraph("<b>Strengths</b>", styles['Heading3']))
            for strength in ai_analysis['strengths']:
                story.append(Paragraph(f"✓ {strength}", styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
        
        # Concerns
        if ai_analysis['concerns']:
            story.append(Paragraph("<b>Areas of Concern</b>", styles['Heading3']))
            for concern in ai_analysis['concerns']:
                story.append(Paragraph(f"⚠ {concern}", styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
        
        # Page break
        story.append(PageBreak())
        
        # Recommendations
        story.append(Paragraph("<b>Personalized Recommendations</b>", styles['Heading2']))
        for i, rec in enumerate(ai_analysis['recommendations'], 1):
            story.append(Paragraph(f"{i}. {rec}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Asset Allocation
        story.append(Paragraph("<b>Recommended Asset Allocation</b>", styles['Heading2']))
        alloc_data = [['Asset Class', 'Allocation']]
        for asset, allocation in ai_analysis['asset_allocation'].items():
            alloc_data.append([asset, allocation])
        
        alloc_table = Table(alloc_data, colWidths=[3*inch, 2*inch])
        alloc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige)
        ]))
        story.append(alloc_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Crypto advice
        story.append(Paragraph("<b>Cryptocurrency Guidance</b>", styles['Heading2']))
        story.append(Paragraph(ai_analysis['crypto_advice'], styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Action steps
        story.append(Paragraph("<b>Immediate Action Steps</b>", styles['Heading2']))
        for i, step in enumerate(ai_analysis['action_steps'], 1):
            story.append(Paragraph(f"{i}. {step}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Risk management
        story.append(Paragraph("<b>Risk Management Strategies</b>", styles['Heading2']))
        for strategy in ai_analysis['risk_management']:
            story.append(Paragraph(f"• {strategy}", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"risk_assessment_{assessment_id}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return jsonify({'error': str(e)}), 500
