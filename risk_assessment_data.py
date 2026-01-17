"""
Advanced Risk Assessment Questions and Scoring System
Multiple comprehensive tests covering different aspects of investment risk tolerance
"""

# Test 1: Financial Situation & Capacity (15 questions)
FINANCIAL_CAPACITY_TEST = {
    'name': 'Financial Capacity Assessment',
    'description': 'Evaluates your current financial situation, income stability, and capacity to take investment risks',
    'weight': 0.25,
    'questions': [
        {
            'id': 'fc1',
            'text': 'What is your current age range?',
            'category': 'Demographics',
            'options': [
                {'value': 1, 'text': 'Under 25', 'points': 10},
                {'value': 2, 'text': '25-35', 'points': 9},
                {'value': 3, 'text': '36-45', 'points': 7},
                {'value': 4, 'text': '46-55', 'points': 5},
                {'value': 5, 'text': '56-65', 'points': 3},
                {'value': 6, 'text': 'Over 65', 'points': 1}
            ]
        },
        {
            'id': 'fc2',
            'text': 'What is your annual household income?',
            'category': 'Income',
            'options': [
                {'value': 1, 'text': 'Less than $30,000', 'points': 2},
                {'value': 2, 'text': '$30,000 - $60,000', 'points': 4},
                {'value': 3, 'text': '$60,000 - $100,000', 'points': 6},
                {'value': 4, 'text': '$100,000 - $150,000', 'points': 8},
                {'value': 5, 'text': 'Over $150,000', 'points': 10}
            ]
        },
        {
            'id': 'fc3',
            'text': 'How stable is your current employment/income source?',
            'category': 'Income Stability',
            'options': [
                {'value': 1, 'text': 'Highly unstable or unemployed', 'points': 1},
                {'value': 2, 'text': 'Somewhat unstable (freelance/gig economy)', 'points': 3},
                {'value': 3, 'text': 'Moderately stable', 'points': 5},
                {'value': 4, 'text': 'Very stable (permanent position)', 'points': 8},
                {'value': 5, 'text': 'Multiple stable income sources', 'points': 10}
            ]
        },
        {
            'id': 'fc4',
            'text': 'What percentage of your income covers essential monthly expenses?',
            'category': 'Financial Flexibility',
            'options': [
                {'value': 1, 'text': 'More than 100% (I have debt)', 'points': 1},
                {'value': 2, 'text': '90-100%', 'points': 2},
                {'value': 3, 'text': '70-90%', 'points': 5},
                {'value': 4, 'text': '50-70%', 'points': 8},
                {'value': 5, 'text': 'Less than 50%', 'points': 10}
            ]
        },
        {
            'id': 'fc5',
            'text': 'How many months of expenses do you have in emergency savings?',
            'category': 'Emergency Fund',
            'options': [
                {'value': 1, 'text': 'Less than 1 month', 'points': 1},
                {'value': 2, 'text': '1-3 months', 'points': 3},
                {'value': 3, 'text': '3-6 months', 'points': 6},
                {'value': 4, 'text': '6-12 months', 'points': 9},
                {'value': 5, 'text': 'More than 12 months', 'points': 10}
            ]
        },
        {
            'id': 'fc6',
            'text': 'What is your total debt-to-income ratio?',
            'category': 'Debt Level',
            'options': [
                {'value': 1, 'text': 'Over 50%', 'points': 1},
                {'value': 2, 'text': '36-50%', 'points': 3},
                {'value': 3, 'text': '20-35%', 'points': 6},
                {'value': 4, 'text': '1-19%', 'points': 9},
                {'value': 5, 'text': 'No debt', 'points': 10}
            ]
        },
        {
            'id': 'fc7',
            'text': 'What is your net worth (assets minus liabilities)?',
            'category': 'Net Worth',
            'options': [
                {'value': 1, 'text': 'Negative', 'points': 1},
                {'value': 2, 'text': '$0 - $50,000', 'points': 3},
                {'value': 3, 'text': '$50,000 - $200,000', 'points': 5},
                {'value': 4, 'text': '$200,000 - $500,000', 'points': 7},
                {'value': 5, 'text': '$500,000 - $1,000,000', 'points': 9},
                {'value': 6, 'text': 'Over $1,000,000', 'points': 10}
            ]
        },
        {
            'id': 'fc8',
            'text': 'Do you have dependents relying on your income?',
            'category': 'Financial Obligations',
            'options': [
                {'value': 1, 'text': 'Yes, multiple dependents with high expenses', 'points': 2},
                {'value': 2, 'text': 'Yes, multiple dependents', 'points': 4},
                {'value': 3, 'text': 'Yes, one dependent', 'points': 6},
                {'value': 4, 'text': 'No dependents, but planning for family', 'points': 8},
                {'value': 5, 'text': 'No dependents', 'points': 10}
            ]
        },
        {
            'id': 'fc9',
            'text': 'What percentage of your income do you currently save/invest?',
            'category': 'Savings Rate',
            'options': [
                {'value': 1, 'text': 'Less than 5%', 'points': 2},
                {'value': 2, 'text': '5-10%', 'points': 4},
                {'value': 3, 'text': '10-20%', 'points': 6},
                {'value': 4, 'text': '20-30%', 'points': 8},
                {'value': 5, 'text': 'More than 30%', 'points': 10}
            ]
        },
        {
            'id': 'fc10',
            'text': 'How would you describe your current insurance coverage?',
            'category': 'Risk Protection',
            'options': [
                {'value': 1, 'text': 'No insurance', 'points': 1},
                {'value': 2, 'text': 'Basic coverage only', 'points': 4},
                {'value': 3, 'text': 'Adequate health and life insurance', 'points': 7},
                {'value': 4, 'text': 'Comprehensive coverage', 'points': 10}
            ]
        },
        {
            'id': 'fc11',
            'text': 'What portion of your assets is currently invested?',
            'category': 'Investment Allocation',
            'options': [
                {'value': 1, 'text': 'None (0%)', 'points': 1},
                {'value': 2, 'text': 'Less than 25%', 'points': 3},
                {'value': 3, 'text': '25-50%', 'points': 6},
                {'value': 4, 'text': '50-75%', 'points': 8},
                {'value': 5, 'text': 'More than 75%', 'points': 10}
            ]
        },
        {
            'id': 'fc12',
            'text': 'Do you expect any major expenses in the next 5 years?',
            'category': 'Future Obligations',
            'options': [
                {'value': 1, 'text': 'Yes, multiple large expenses', 'points': 2},
                {'value': 2, 'text': 'Yes, one major expense', 'points': 4},
                {'value': 3, 'text': 'Possibly one expense', 'points': 6},
                {'value': 4, 'text': 'Unlikely', 'points': 8},
                {'value': 5, 'text': 'No major expenses expected', 'points': 10}
            ]
        },
        {
            'id': 'fc13',
            'text': 'What is your expected retirement age?',
            'category': 'Time Horizon',
            'options': [
                {'value': 1, 'text': 'Within 5 years', 'points': 2},
                {'value': 2, 'text': '5-10 years', 'points': 4},
                {'value': 3, 'text': '10-20 years', 'points': 6},
                {'value': 4, 'text': '20-30 years', 'points': 8},
                {'value': 5, 'text': 'More than 30 years', 'points': 10}
            ]
        },
        {
            'id': 'fc14',
            'text': 'Do you have other sources of retirement income (pension, rental income, etc.)?',
            'category': 'Retirement Security',
            'options': [
                {'value': 1, 'text': 'No other sources', 'points': 3},
                {'value': 2, 'text': 'One uncertain source', 'points': 5},
                {'value': 3, 'text': 'One reliable source', 'points': 7},
                {'value': 4, 'text': 'Multiple reliable sources', 'points': 10}
            ]
        },
        {
            'id': 'fc15',
            'text': 'How liquid are your current assets?',
            'category': 'Liquidity',
            'options': [
                {'value': 1, 'text': 'Most are illiquid (real estate, locked investments)', 'points': 3},
                {'value': 2, 'text': 'Somewhat liquid', 'points': 5},
                {'value': 3, 'text': 'Moderately liquid', 'points': 7},
                {'value': 4, 'text': 'Highly liquid (cash, stocks, ETFs)', 'points': 10}
            ]
        }
    ]
}

# Test 2: Investment Knowledge & Experience (15 questions)
INVESTMENT_KNOWLEDGE_TEST = {
    'name': 'Investment Knowledge & Experience',
    'description': 'Assesses your understanding of investment concepts, market dynamics, and practical experience',
    'weight': 0.20,
    'questions': [
        {
            'id': 'ik1',
            'text': 'How many years of investing experience do you have?',
            'category': 'Experience',
            'options': [
                {'value': 1, 'text': 'None', 'points': 1},
                {'value': 2, 'text': 'Less than 1 year', 'points': 3},
                {'value': 3, 'text': '1-3 years', 'points': 5},
                {'value': 4, 'text': '3-7 years', 'points': 7},
                {'value': 5, 'text': '7-15 years', 'points': 9},
                {'value': 6, 'text': 'More than 15 years', 'points': 10}
            ]
        },
        {
            'id': 'ik2',
            'text': 'Which investment vehicles have you personally used?',
            'category': 'Practical Experience',
            'options': [
                {'value': 1, 'text': 'None', 'points': 1},
                {'value': 2, 'text': 'Savings accounts only', 'points': 2},
                {'value': 3, 'text': 'Stocks or mutual funds', 'points': 5},
                {'value': 4, 'text': 'Stocks, bonds, ETFs, mutual funds', 'points': 7},
                {'value': 5, 'text': 'Full range including options, futures, crypto', 'points': 10}
            ]
        },
        {
            'id': 'ik3',
            'text': 'What is your understanding of portfolio diversification?',
            'category': 'Conceptual Knowledge',
            'options': [
                {'value': 1, 'text': 'Not familiar with the concept', 'points': 1},
                {'value': 2, 'text': 'Heard of it but don\'t understand', 'points': 3},
                {'value': 3, 'text': 'Basic understanding', 'points': 5},
                {'value': 4, 'text': 'Good understanding and practice it', 'points': 8},
                {'value': 5, 'text': 'Expert level understanding', 'points': 10}
            ]
        },
        {
            'id': 'ik4',
            'text': 'How familiar are you with reading financial statements?',
            'category': 'Technical Skills',
            'options': [
                {'value': 1, 'text': 'Not familiar at all', 'points': 2},
                {'value': 2, 'text': 'Can understand basics', 'points': 4},
                {'value': 3, 'text': 'Can analyze income statements', 'points': 6},
                {'value': 4, 'text': 'Can analyze all major statements', 'points': 8},
                {'value': 5, 'text': 'Professional level analysis', 'points': 10}
            ]
        },
        {
            'id': 'ik5',
            'text': 'Do you understand the relationship between risk and return?',
            'category': 'Risk Concept',
            'options': [
                {'value': 1, 'text': 'No understanding', 'points': 1},
                {'value': 2, 'text': 'Vague understanding', 'points': 4},
                {'value': 3, 'text': 'Clear understanding', 'points': 7},
                {'value': 4, 'text': 'Can explain to others', 'points': 10}
            ]
        },
        {
            'id': 'ik6',
            'text': 'Have you experienced a significant market downturn with your investments?',
            'category': 'Market Experience',
            'options': [
                {'value': 1, 'text': 'No', 'points': 3},
                {'value': 2, 'text': 'Yes, and it made me very uncomfortable', 'points': 4},
                {'value': 3, 'text': 'Yes, I held my positions', 'points': 7},
                {'value': 4, 'text': 'Yes, I bought more during the dip', 'points': 10}
            ]
        },
        {
            'id': 'ik7',
            'text': 'How do you typically research investments before buying?',
            'category': 'Research Approach',
            'options': [
                {'value': 1, 'text': 'I don\'t research, follow tips', 'points': 1},
                {'value': 2, 'text': 'Quick online search', 'points': 3},
                {'value': 3, 'text': 'Review basic metrics and news', 'points': 6},
                {'value': 4, 'text': 'Thorough fundamental analysis', 'points': 8},
                {'value': 5, 'text': 'Comprehensive quantitative and qualitative analysis', 'points': 10}
            ]
        },
        {
            'id': 'ik8',
            'text': 'What is your understanding of asset allocation strategies?',
            'category': 'Portfolio Management',
            'options': [
                {'value': 1, 'text': 'Not familiar', 'points': 2},
                {'value': 2, 'text': 'Heard of it', 'points': 4},
                {'value': 3, 'text': 'Understand and use basic allocation', 'points': 6},
                {'value': 4, 'text': 'Actively manage and rebalance', 'points': 8},
                {'value': 5, 'text': 'Use advanced strategic allocation', 'points': 10}
            ]
        },
        {
            'id': 'ik9',
            'text': 'How familiar are you with technical analysis (chart patterns, indicators)?',
            'category': 'Technical Analysis',
            'options': [
                {'value': 1, 'text': 'Not familiar', 'points': 3},
                {'value': 2, 'text': 'Know some basics', 'points': 5},
                {'value': 3, 'text': 'Use regularly', 'points': 7},
                {'value': 4, 'text': 'Expert practitioner', 'points': 10}
            ]
        },
        {
            'id': 'ik10',
            'text': 'Do you understand the impact of inflation on investments?',
            'category': 'Economic Knowledge',
            'options': [
                {'value': 1, 'text': 'No', 'points': 2},
                {'value': 2, 'text': 'Basic understanding', 'points': 5},
                {'value': 3, 'text': 'Good understanding', 'points': 8},
                {'value': 4, 'text': 'Factor it into all decisions', 'points': 10}
            ]
        },
        {
            'id': 'ik11',
            'text': 'Have you ever used leverage or margin in trading?',
            'category': 'Advanced Strategies',
            'options': [
                {'value': 1, 'text': 'No, don\'t understand it', 'points': 3},
                {'value': 2, 'text': 'Understand but never used', 'points': 5},
                {'value': 3, 'text': 'Used cautiously with small amounts', 'points': 7},
                {'value': 4, 'text': 'Use regularly with risk management', 'points': 10}
            ]
        },
        {
            'id': 'ik12',
            'text': 'How well do you understand cryptocurrency and blockchain technology?',
            'category': 'Crypto Knowledge',
            'options': [
                {'value': 1, 'text': 'No understanding', 'points': 2},
                {'value': 2, 'text': 'Heard about it', 'points': 4},
                {'value': 3, 'text': 'Basic understanding', 'points': 6},
                {'value': 4, 'text': 'Good understanding and own crypto', 'points': 8},
                {'value': 5, 'text': 'Expert level knowledge', 'points': 10}
            ]
        },
        {
            'id': 'ik13',
            'text': 'Do you regularly review and adjust your portfolio?',
            'category': 'Active Management',
            'options': [
                {'value': 1, 'text': 'Rarely or never', 'points': 2},
                {'value': 2, 'text': 'Once a year', 'points': 5},
                {'value': 3, 'text': 'Quarterly', 'points': 7},
                {'value': 4, 'text': 'Monthly or more often', 'points': 10}
            ]
        },
        {
            'id': 'ik14',
            'text': 'What sources do you use to stay informed about markets?',
            'category': 'Information Sources',
            'options': [
                {'value': 1, 'text': 'Don\'t actively follow markets', 'points': 1},
                {'value': 2, 'text': 'Social media only', 'points': 3},
                {'value': 3, 'text': 'News websites and apps', 'points': 6},
                {'value': 4, 'text': 'Professional financial publications', 'points': 8},
                {'value': 5, 'text': 'Multiple professional sources + analysis tools', 'points': 10}
            ]
        },
        {
            'id': 'ik15',
            'text': 'Have you taken any investment courses or obtained certifications?',
            'category': 'Formal Education',
            'options': [
                {'value': 1, 'text': 'No formal education', 'points': 3},
                {'value': 2, 'text': 'Self-taught through online resources', 'points': 5},
                {'value': 3, 'text': 'Completed some courses', 'points': 7},
                {'value': 4, 'text': 'Finance degree or professional certification', 'points': 10}
            ]
        }
    ]
}

# Test 3: Psychological Risk Tolerance (15 questions)
PSYCHOLOGICAL_TOLERANCE_TEST = {
    'name': 'Psychological Risk Tolerance',
    'description': 'Evaluates your emotional response to market volatility and investment losses',
    'weight': 0.30,
    'questions': [
        {
            'id': 'pt1',
            'text': 'Your portfolio drops 10% in a week. What\'s your immediate reaction?',
            'category': 'Volatility Response',
            'options': [
                {'value': 1, 'text': 'Panic and sell everything immediately', 'points': 1},
                {'value': 2, 'text': 'Feel very anxious and consider selling', 'points': 3},
                {'value': 3, 'text': 'Feel concerned but take no action', 'points': 6},
                {'value': 4, 'text': 'Stay calm and review fundamentals', 'points': 8},
                {'value': 5, 'text': 'See it as a buying opportunity', 'points': 10}
            ]
        },
        {
            'id': 'pt2',
            'text': 'Your investment loses 30% of its value over 3 months. You:',
            'category': 'Loss Response',
            'options': [
                {'value': 1, 'text': 'Sell immediately to prevent more losses', 'points': 1},
                {'value': 2, 'text': 'Sell half to limit further losses', 'points': 3},
                {'value': 3, 'text': 'Hold and hope it recovers', 'points': 5},
                {'value': 4, 'text': 'Hold and reassess strategy', 'points': 7},
                {'value': 5, 'text': 'Buy more to average down', 'points': 10}
            ]
        },
        {
            'id': 'pt3',
            'text': 'How often do you check your investment portfolio?',
            'category': 'Monitoring Behavior',
            'options': [
                {'value': 1, 'text': 'Multiple times daily', 'points': 3},
                {'value': 2, 'text': 'Once daily', 'points': 5},
                {'value': 3, 'text': 'Few times a week', 'points': 7},
                {'value': 4, 'text': 'Weekly', 'points': 9},
                {'value': 5, 'text': 'Monthly or less', 'points': 10}
            ]
        },
        {
            'id': 'pt4',
            'text': 'You invest $10,000. What\'s the maximum loss you could handle psychologically?',
            'category': 'Loss Tolerance',
            'options': [
                {'value': 1, 'text': '$500 (5%)', 'points': 2},
                {'value': 2, 'text': '$1,000 (10%)', 'points': 4},
                {'value': 3, 'text': '$2,000 (20%)', 'points': 6},
                {'value': 4, 'text': '$3,000 (30%)', 'points': 8},
                {'value': 5, 'text': '$5,000+ (50%+)', 'points': 10}
            ]
        },
        {
            'id': 'pt5',
            'text': 'How do you feel after making an investment decision?',
            'category': 'Decision Confidence',
            'options': [
                {'value': 1, 'text': 'Very anxious and second-guess constantly', 'points': 2},
                {'value': 2, 'text': 'Somewhat worried', 'points': 4},
                {'value': 3, 'text': 'Neutral, monitor regularly', 'points': 7},
                {'value': 4, 'text': 'Confident in my research', 'points': 9},
                {'value': 5, 'text': 'Very confident, set and forget', 'points': 10}
            ]
        },
        {
            'id': 'pt6',
            'text': 'Your friend\'s risky investment doubles while yours grows 10%. You feel:',
            'category': 'FOMO Response',
            'options': [
                {'value': 1, 'text': 'Regretful and want to chase similar returns', 'points': 3},
                {'value': 2, 'text': 'Somewhat envious', 'points': 5},
                {'value': 3, 'text': 'Happy for them, stay with my strategy', 'points': 8},
                {'value': 4, 'text': 'Indifferent, everyone\'s risk is different', 'points': 10}
            ]
        },
        {
            'id': 'pt7',
            'text': 'How do you typically make investment decisions?',
            'category': 'Decision Making Style',
            'options': [
                {'value': 1, 'text': 'Based on tips or emotions', 'points': 2},
                {'value': 2, 'text': 'Quick decisions with basic research', 'points': 4},
                {'value': 3, 'text': 'Careful consideration with research', 'points': 7},
                {'value': 4, 'text': 'Systematic approach with predetermined criteria', 'points': 10}
            ]
        },
        {
            'id': 'pt8',
            'text': 'During a market crash, you:',
            'category': 'Crisis Response',
            'options': [
                {'value': 1, 'text': 'Panic sell to avoid further losses', 'points': 1},
                {'value': 2, 'text': 'Sell some positions', 'points': 3},
                {'value': 3, 'text': 'Hold all positions', 'points': 6},
                {'value': 4, 'text': 'Hold and look for opportunities', 'points': 8},
                {'value': 5, 'text': 'Aggressively buy the dip', 'points': 10}
            ]
        },
        {
            'id': 'pt9',
            'text': 'How do investment losses affect your sleep and daily life?',
            'category': 'Stress Impact',
            'options': [
                {'value': 1, 'text': 'Severely - can\'t sleep, constant worry', 'points': 1},
                {'value': 2, 'text': 'Moderately - frequent worry', 'points': 3},
                {'value': 3, 'text': 'Somewhat - occasional concern', 'points': 6},
                {'value': 4, 'text': 'Minimally - rare concern', 'points': 8},
                {'value': 5, 'text': 'Not at all - expected part of investing', 'points': 10}
            ]
        },
        {
            'id': 'pt10',
            'text': 'Would you prefer:',
            'category': 'Risk vs Reward Preference',
            'options': [
                {'value': 1, 'text': '100% chance of gaining $1,000', 'points': 2},
                {'value': 2, 'text': '80% chance of gaining $1,500', 'points': 5},
                {'value': 3, 'text': '50% chance of gaining $3,000', 'points': 7},
                {'value': 4, 'text': '25% chance of gaining $7,000', 'points': 9},
                {'value': 5, 'text': '10% chance of gaining $20,000', 'points': 10}
            ]
        },
        {
            'id': 'pt11',
            'text': 'How do you react to conflicting investment advice?',
            'category': 'Information Processing',
            'options': [
                {'value': 1, 'text': 'Feel confused and paralyzed', 'points': 2},
                {'value': 2, 'text': 'Follow the most recent advice', 'points': 4},
                {'value': 3, 'text': 'Do more research', 'points': 7},
                {'value': 4, 'text': 'Analyze both sides and trust my judgment', 'points': 10}
            ]
        },
        {
            'id': 'pt12',
            'text': 'You miss out on a great investment opportunity. You:',
            'category': 'Regret Handling',
            'options': [
                {'value': 1, 'text': 'Feel deep regret for weeks', 'points': 2},
                {'value': 2, 'text': 'Feel disappointed for a few days', 'points': 5},
                {'value': 3, 'text': 'Accept it and move on quickly', 'points': 8},
                {'value': 4, 'text': 'Learn from it without emotional attachment', 'points': 10}
            ]
        },
        {
            'id': 'pt13',
            'text': 'How comfortable are you with uncertainty?',
            'category': 'Uncertainty Tolerance',
            'options': [
                {'value': 1, 'text': 'Very uncomfortable, need certainty', 'points': 2},
                {'value': 2, 'text': 'Somewhat uncomfortable', 'points': 4},
                {'value': 3, 'text': 'Neutral', 'points': 6},
                {'value': 4, 'text': 'Fairly comfortable', 'points': 8},
                {'value': 5, 'text': 'Very comfortable, embrace it', 'points': 10}
            ]
        },
        {
            'id': 'pt14',
            'text': 'Your investment is volatile but trending up long-term. You:',
            'category': 'Long-term Focus',
            'options': [
                {'value': 1, 'text': 'Can\'t handle the swings, sell', 'points': 2},
                {'value': 2, 'text': 'Reduce position to reduce anxiety', 'points': 4},
                {'value': 3, 'text': 'Hold but check frequently', 'points': 6},
                {'value': 4, 'text': 'Hold with confidence', 'points': 8},
                {'value': 5, 'text': 'Add more during dips', 'points': 10}
            ]
        },
        {
            'id': 'pt15',
            'text': 'How do you view investment risk?',
            'category': 'Risk Philosophy',
            'options': [
                {'value': 1, 'text': 'Something to avoid at all costs', 'points': 2},
                {'value': 2, 'text': 'Necessary evil to accept minimally', 'points': 4},
                {'value': 3, 'text': 'Part of investing, manage carefully', 'points': 7},
                {'value': 4, 'text': 'Opportunity when managed properly', 'points': 10}
            ]
        }
    ]
}

# Test 4: Investment Goals & Time Horizon (10 questions)
GOALS_TIMELINE_TEST = {
    'name': 'Investment Goals & Time Horizon',
    'description': 'Assesses your investment objectives, time frames, and liquidity needs',
    'weight': 0.25,
    'questions': [
        {
            'id': 'gt1',
            'text': 'What is your primary investment goal?',
            'category': 'Primary Objective',
            'options': [
                {'value': 1, 'text': 'Capital preservation (protect what I have)', 'points': 2},
                {'value': 2, 'text': 'Generate current income', 'points': 4},
                {'value': 3, 'text': 'Balanced growth and income', 'points': 6},
                {'value': 4, 'text': 'Long-term capital appreciation', 'points': 8},
                {'value': 5, 'text': 'Aggressive growth / maximum returns', 'points': 10}
            ]
        },
        {
            'id': 'gt2',
            'text': 'When do you plan to withdraw a significant portion (>25%) of your investments?',
            'category': 'Withdrawal Timeline',
            'options': [
                {'value': 1, 'text': 'Within 1 year', 'points': 1},
                {'value': 2, 'text': '1-3 years', 'points': 3},
                {'value': 3, 'text': '3-5 years', 'points': 5},
                {'value': 4, 'text': '5-10 years', 'points': 7},
                {'value': 5, 'text': '10-20 years', 'points': 9},
                {'value': 6, 'text': 'More than 20 years', 'points': 10}
            ]
        },
        {
            'id': 'gt3',
            'text': 'What percentage of your investments might you need to access in an emergency?',
            'category': 'Liquidity Needs',
            'options': [
                {'value': 1, 'text': 'More than 50%', 'points': 2},
                {'value': 2, 'text': '25-50%', 'points': 4},
                {'value': 3, 'text': '10-25%', 'points': 7},
                {'value': 4, 'text': 'Less than 10%', 'points': 9},
                {'value': 5, 'text': 'None, have separate emergency fund', 'points': 10}
            ]
        },
        {
            'id': 'gt4',
            'text': 'Are you investing for a specific goal (house, education, retirement)?',
            'category': 'Goal Specificity',
            'options': [
                {'value': 1, 'text': 'Yes, need funds within 2 years', 'points': 2},
                {'value': 2, 'text': 'Yes, need funds in 2-5 years', 'points': 4},
                {'value': 3, 'text': 'Yes, need funds in 5-10 years', 'points': 7},
                {'value': 4, 'text': 'Yes, but distant future (10+ years)', 'points': 9},
                {'value': 5, 'text': 'No specific goal, general wealth building', 'points': 10}
            ]
        },
        {
            'id': 'gt5',
            'text': 'How important is it to outperform market averages?',
            'category': 'Performance Expectations',
            'options': [
                {'value': 1, 'text': 'Not important, just want to match inflation', 'points': 2},
                {'value': 2, 'text': 'Somewhat important', 'points': 5},
                {'value': 3, 'text': 'Important, willing to take moderate risk', 'points': 7},
                {'value': 4, 'text': 'Very important, willing to take high risk', 'points': 10}
            ]
        },
        {
            'id': 'gt6',
            'text': 'What annual return would make you satisfied?',
            'category': 'Return Expectations',
            'options': [
                {'value': 1, 'text': '2-4% (beat inflation)', 'points': 2},
                {'value': 2, 'text': '5-7%', 'points': 4},
                {'value': 3, 'text': '8-10%', 'points': 6},
                {'value': 4, 'text': '11-15%', 'points': 8},
                {'value': 5, 'text': 'More than 15%', 'points': 10}
            ]
        },
        {
            'id': 'gt7',
            'text': 'Would you accept lower returns for lower risk?',
            'category': 'Risk-Return Trade-off',
            'options': [
                {'value': 1, 'text': 'Yes, much prefer safety', 'points': 2},
                {'value': 2, 'text': 'Yes, somewhat prefer safety', 'points': 5},
                {'value': 3, 'text': 'Neutral', 'points': 7},
                {'value': 4, 'text': 'No, prefer higher potential returns', 'points': 10}
            ]
        },
        {
            'id': 'gt8',
            'text': 'If your investment significantly outperforms, would you:',
            'category': 'Profit Taking Strategy',
            'options': [
                {'value': 1, 'text': 'Take profits immediately', 'points': 3},
                {'value': 2, 'text': 'Take some profits', 'points': 5},
                {'value': 3, 'text': 'Let it run', 'points': 8},
                {'value': 4, 'text': 'Add more to winning position', 'points': 10}
            ]
        },
        {
            'id': 'gt9',
            'text': 'How flexible are your investment timelines?',
            'category': 'Timeline Flexibility',
            'options': [
                {'value': 1, 'text': 'Not flexible, fixed dates', 'points': 3},
                {'value': 2, 'text': 'Somewhat flexible (1-2 years)', 'points': 6},
                {'value': 3, 'text': 'Very flexible', 'points': 10}
            ]
        },
        {
            'id': 'gt10',
            'text': 'Are you building wealth for yourself or heirs?',
            'category': 'Wealth Legacy',
            'options': [
                {'value': 1, 'text': 'Primarily for my own use soon', 'points': 3},
                {'value': 2, 'text': 'For my retirement', 'points': 6},
                {'value': 3, 'text': 'Mix of retirement and heirs', 'points': 8},
                {'value': 4, 'text': 'Primarily for heirs / long-term legacy', 'points': 10}
            ]
        }
    ]
}

# Scoring interpretation
RISK_CATEGORIES = [
    {
        'level': 'Ultra Conservative',
        'range': (0, 20),
        'description': 'Extremely risk-averse with focus on capital preservation',
        'allocation': {
            'Cash': '20-30%',
            'Bonds': '60-70%',
            'Stocks': '5-10%',
            'Alternative': '0-5%'
        },
        'crypto_allocation': '0-2%',
        'recommendation': 'Focus on stable, income-generating assets with minimal volatility'
    },
    {
        'level': 'Conservative',
        'range': (20, 35),
        'description': 'Risk-averse with preference for stability over growth',
        'allocation': {
            'Cash': '10-20%',
            'Bonds': '50-60%',
            'Stocks': '20-30%',
            'Alternative': '5-10%'
        },
        'crypto_allocation': '2-5%',
        'recommendation': 'Prioritize capital preservation with modest growth potential'
    },
    {
        'level': 'Moderately Conservative',
        'range': (35, 45),
        'description': 'Balanced approach leaning toward stability',
        'allocation': {
            'Cash': '5-10%',
            'Bonds': '40-50%',
            'Stocks': '35-45%',
            'Alternative': '5-10%'
        },
        'crypto_allocation': '3-7%',
        'recommendation': 'Balanced portfolio with emphasis on risk management'
    },
    {
        'level': 'Moderate',
        'range': (45, 55),
        'description': 'Balanced between growth and stability',
        'allocation': {
            'Cash': '5-10%',
            'Bonds': '30-40%',
            'Stocks': '45-55%',
            'Alternative': '5-15%'
        },
        'crypto_allocation': '5-10%',
        'recommendation': 'Diversified portfolio balancing growth and income'
    },
    {
        'level': 'Moderately Aggressive',
        'range': (55, 65),
        'description': 'Growth-focused with calculated risk-taking',
        'allocation': {
            'Cash': '0-5%',
            'Bonds': '20-30%',
            'Stocks': '60-70%',
            'Alternative': '5-15%'
        },
        'crypto_allocation': '7-12%',
        'recommendation': 'Growth-oriented with diversified equity exposure'
    },
    {
        'level': 'Aggressive',
        'range': (65, 75),
        'description': 'High growth focus with substantial risk tolerance',
        'allocation': {
            'Cash': '0-5%',
            'Bonds': '10-15%',
            'Stocks': '70-80%',
            'Alternative': '10-20%'
        },
        'crypto_allocation': '10-15%',
        'recommendation': 'Maximum equity exposure with alternative investments'
    },
    {
        'level': 'Very Aggressive',
        'range': (75, 100),
        'description': 'Maximum growth potential with very high risk tolerance',
        'allocation': {
            'Cash': '0-5%',
            'Bonds': '0-10%',
            'Stocks': '75-85%',
            'Alternative': '15-25%'
        },
        'crypto_allocation': '12-20%',
        'recommendation': 'Aggressive growth strategy with high-risk, high-reward assets'
    }
]

# AI Analysis prompts
def get_ai_analysis_prompt(scores, user_data):
    return f"""
You are an expert financial advisor analyzing an investor's risk profile. Based on the comprehensive assessment results:

Financial Capacity Score: {scores['financial']}% (Weight: 25%)
Investment Knowledge Score: {scores['knowledge']}% (Weight: 20%)
Psychological Tolerance Score: {scores['psychological']}% (Weight: 30%)
Goals & Timeline Score: {scores['goals']}% (Weight: 25%)

Overall Risk Score: {scores['total']}%
Risk Category: {scores['category']}

User Demographics:
- Age Range: {user_data.get('age', 'Not provided')}
- Experience: {user_data.get('experience', 'Not provided')}
- Primary Goal: {user_data.get('goal', 'Not provided')}
- Time Horizon: {user_data.get('timeline', 'Not provided')}

Provide a comprehensive analysis covering:
1. **Risk Profile Summary**: Detailed interpretation of their overall risk tolerance
2. **Strengths**: What aspects of their profile support their risk capacity
3. **Areas of Concern**: Any red flags or mismatches between capacity and tolerance
4. **Personalized Recommendations**: Specific investment strategies suited to their profile
5. **Asset Allocation Guidance**: Detailed breakdown of recommended portfolio mix
6. **Crypto Investment Advice**: Specific guidance on cryptocurrency allocation
7. **Action Steps**: 3-5 concrete next steps they should take
8. **Risk Management**: Strategies to manage their specific risk profile

Be specific, actionable, and educational. Format with clear headings and bullet points.
"""
