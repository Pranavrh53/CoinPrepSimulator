let currentChart = null;

function renderInteractiveChart(canvasId, coinId, coinName) {
    fetch(`/historical/${coinId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Failed to load historical data:', data.error);
                return;
            }

            if (currentChart) {
                currentChart.destroy();
            }

            const ctx = document.getElementById(canvasId).getContext('2d');
            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.dates,
                    datasets: [
                        {
                            label: `${coinName} Price (USD)`,
                            data: data.prices,
                            borderColor: 'blue',
                            yAxisID: 'y-price',
                            fill: false
                        },
                        {
                            label: `${coinName} Volume (USD)`,
                            data: data.volumes,
                            borderColor: 'green',
                            yAxisID: 'y-volume',
                            fill: false,
                            hidden: true
                        },
                        {
                            label: `${coinName} Market Cap (USD)`,
                            data: data.market_caps,
                            borderColor: 'red',
                            yAxisID: 'y-market-cap',
                            fill: false,
                            hidden: true
                        }
                    ]
                },
                options: {
                    responsive: true,
                    scales: {
                        'y-price': {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {
                                display: true,
                                text: 'Price (USD)'
                            }
                        },
                        'y-volume': {
                            type: 'linear',
                            display: false,
                            position: 'right',
                            title: {
                                display: true,
                                text: 'Volume (USD)'
                            },
                            grid: {
                                drawOnChartArea: false
                            }
                        },
                        'y-market-cap': {
                            type: 'linear',
                            display: false,
                            position: 'right',
                            title: {
                                display: true,
                                text: 'Market Cap (USD)'
                            },
                            grid: {
                                drawOnChartArea: false
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            onClick: (e, legendItem, legend) => {
                                const index = legendItem.datasetIndex;
                                const ci = legend.chart;
                                ci.getDatasetMeta(index).hidden = !ci.getDatasetMeta(index).hidden;
                                ci.update();
                            }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        }
                    },
                    interaction: {
                        mode: 'nearest',
                        axis: 'x',
                        intersect: false
                    }
                }
            });
        })
        .catch(error => console.error('Error fetching historical data:', error));
}

function renderCorrelationHeatmap(canvasId, correlationData) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    const labels = correlationData.labels || [];
    const matrix = correlationData.matrix || [];

    if (!labels.length || !matrix.length) {
        ctx.font = '16px Arial';
        ctx.fillText('No correlation data available', 10, 50);
        return;
    }

    const data = {
        labels: labels,
        datasets: [{
            label: 'Correlation',
            data: matrix.flatMap((row, i) => 
                row.map((value, j) => ({
                    x: labels[i],
                    y: labels[j],
                    v: value
                }))
            ),
            backgroundColor: (context) => {
                const value = context.dataset.data[context.dataIndex].v;
                const r = Math.floor(255 * (1 - Math.abs(value)));
                const b = Math.floor(255 * Math.abs(value));
                return `rgb(${r}, 0, ${b})`;
            },
            borderColor: 'black',
            borderWidth: 1
        }]
    };

    new Chart(ctx, {
        type: 'matrix',
        data: data,
        options: {
            responsive: true,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Coins'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Coins'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const v = context.raw.v;
                            return `Correlation: ${v.toFixed(2)}`;
                        }
                    }
                }
            }
        }
    });
}