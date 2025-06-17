document.addEventListener('DOMContentLoaded', () => {
    const predictionDateInput = document.getElementById('predictionDate');
    const fetchDataButton = document.getElementById('fetchDataButton');
    const loadingSection = document.getElementById('loading');
    const predictionResultsSection = document.getElementById('predictionResults');
    const errorDisplaySection = document.getElementById('errorDisplay');

    const dataPrevisaoSpan = document.getElementById('dataPrevisao');
    const totalPrevistoHojeP = document.getElementById('totalPrevistoHoje');
    const top3MotoristasDestaqueUl = document.getElementById('top3MotoristasDestaque');
    const top10MotoristasGeralUl = document.getElementById('top10MotoristasGeral');
    const eventosEspecificosDiv = document.getElementById('eventosEspecificos');
    const top3LocalidadesUl = document.getElementById('top3Localidades'); // NOVO: elemento para localidades
    const errorMessageP = document.getElementById('errorMessage');
    const errorDetailsP = document.getElementById('errorDetails');

    const BACKEND_URL = 'https://ia-previsao-ritmo-backend.onrender.com';

    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);
    predictionDateInput.value = tomorrow.toISOString().split('T')[0];

    fetchDataButton.addEventListener('click', async () => {
        const selectedDate = predictionDateInput.value;
        if (!selectedDate) {
            alert('Por favor, selecione uma data para a previsão.');
            return;
        }

        predictionResultsSection.classList.add('hidden');
        errorDisplaySection.classList.add('hidden');
        loadingSection.classList.remove('hidden');

        try {
            const response = await fetch(`${BACKEND_URL}/predict?date=${selectedDate}`);
            const data = await response.json();

            if (!response.ok) {
                errorMessageP.textContent = data.error || "Erro desconhecido na previsão.";
                errorDetailsP.textContent = `Data solicitada: ${data.requested_date || 'N/A'}, Período da Previsão: ${data.forecast_period_start || 'N/A'} a ${data.forecast_period_end || 'N/A'}.`;
                errorDisplaySection.classList.remove('hidden');
                loadingSection.classList.add('hidden');
                return;
            }

            // Popula o card principal (data e total previsto)
            dataPrevisaoSpan.textContent = data.data_previsao;
            if (data.previsao_total_yhat1 !== null && data.previsao_total_yhat1 !== undefined) {
                totalPrevistoHojeP.textContent = data.previsao_total_yhat1.toFixed(2);
            } else {
                totalPrevistoHojeP.textContent = "N/A";
            }

            // Limpa as listas antes de popular
            top3MotoristasDestaqueUl.innerHTML = '';
            top10MotoristasGeralUl.innerHTML = '';
            top3LocalidadesUl.innerHTML = ''; // NOVO: limpa a lista de localidades

            // Top Motoristas
            if (data.top_10_motoristas_geral && data.top_10_motoristas_geral.length > 0) {
                // Top 3 Motoristas em Destaque
                data.top_10_motoristas_geral.slice(0, 3).forEach(motorista => {
                    const li = document.createElement('li');
                    const probabilidade = motorista.Probabilidade;
                    li.innerHTML = `<span class="driver-name">${motorista.Motorista}</span> <span class="driver-prob">${probabilidade !== null && probabilidade !== undefined ? probabilidade.toFixed(2).replace('.', ',') + '%' : 'N/A'}</span>`;
                    top3MotoristasDestaqueUl.appendChild(li);
                });

                // Outros Motoristas (Top 4-10)
                if (data.top_10_motoristas_geral.length > 3) {
                    data.top_10_motoristas_geral.slice(3, 10).forEach(motorista => {
                        const li = document.createElement('li');
                        const probabilidade = motorista.Probabilidade;
                        li.textContent = `${motorista.Motorista}: ${probabilidade !== null && probabilidade !== undefined ? probabilidade.toFixed(2).replace('.', ',') + '%' : 'N/A'}`;
                        top10MotoristasGeralUl.appendChild(li);
                    });
                } else {
                    top10MotoristasGeralUl.innerHTML = '<li>Não há motoristas adicionais no Top 10.</li>';
                }
            } else {
                top3MotoristasDestaqueUl.innerHTML = '<li>Nenhum motorista encontrado no top 3.</li>';
                top10MotoristasGeralUl.innerHTML = '<li>Nenhum motorista encontrado no top 10.</li>';
            }

            // Probabilidade por Tipo de Evento
            eventosEspecificosDiv.innerHTML = '';
            if (data.probabilidade_eventos_especificos) {
                for (const evento in data.probabilidade_eventos_especificos) {
                    const eventCard = document.createElement('div');
                    eventCard.classList.add('event-detail-card');
                    eventCard.innerHTML = `<h3>${evento}</h3>`;
                    const ul = document.createElement('ul');

                    const eventoData = data.probabilidade_eventos_especificos[evento];
                    if (Array.isArray(eventoData) && eventoData.length > 0) {
                        eventoData.forEach(motorista => {
                            const li = document.createElement('li');
                            const probabilidade = motorista.Probabilidade;
                            li.textContent = `${motorista.Motorista}: ${probabilidade !== null && probabilidade !== undefined ? probabilidade.toFixed(2).replace('.', ',') + '%' : 'N/A'}`;
                            ul.appendChild(li);
                        });
                    } else if (eventoData.message) {
                        ul.innerHTML = `<li>${eventoData.message}</li>`;
                    } else if (eventoData.error) {
                        ul.innerHTML = `<li>Erro: ${eventoData.error}</li>`;
                    } else {
                        ul.innerHTML = `<li>Nenhum dado detalhado encontrado para este evento.</li>`;
                    }
                    eventCard.appendChild(ul);
                    eventosEspecificosDiv.appendChild(eventCard);
                }
            } else {
                eventosEspecificosDiv.innerHTML = '<p>Nenhuma probabilidade por tipo de evento disponível.</p>';
            }

            // NOVO: Probabilidade por Localidade
            if (data.top_3_localidades && data.top_3_localidades.length > 0) {
                data.top_3_localidades.forEach(localidade => {
                    const li = document.createElement('li');
                    const probabilidade = localidade.Probabilidade;
                    li.innerHTML = `<span class="location-name">${localidade.Localidade}</span> <span class="location-prob">${probabilidade !== null && probabilidade !== undefined ? probabilidade.toFixed(2).replace('.', ',') + '%' : 'N/A'}</span>`;
                    top3LocalidadesUl.appendChild(li);
                });
            } else {
                top3LocalidadesUl.innerHTML = '<li>Nenhuma localidade encontrada.</li>';
            }


            predictionResultsSection.classList.remove('hidden');
            loadingSection.classList.add('hidden');

        } catch (error) {
            console.error('Erro ao buscar dados:', error);
            errorMessageP.textContent = 'Não foi possível conectar ao servidor de previsão.';
            errorDetailsP.textContent = 'Verifique sua conexão com a internet ou se o serviço de backend está ativo.';
            errorDisplaySection.classList.remove('hidden'); // Exibe a seção de erro
            loadingSection.classList.add('hidden');
        }
    });

    fetchDataButton.click();
});
