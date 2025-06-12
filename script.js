document.addEventListener('DOMContentLoaded', () => {
    const predictionDateInput = document.getElementById('predictionDate');
    const fetchDataButton = document.getElementById('fetchDataButton');
    const loadingSection = document.getElementById('loading');
    const predictionResultsSection = document.getElementById('predictionResults');
    const errorDisplaySection = document.getElementById('errorDisplay');

    const dataPrevisaoSpan = document.getElementById('dataPrevisao');
    const totalPrevistoHojeP = document.getElementById('totalPrevistoHoje');
    // REMOVIDO: const detalhesPrevisaoUl = document.getElementById('detalhesPrevisao');
    const top10MotoristasGeralUl = document.getElementById('top10MotoristasGeral');
    const eventosEspecificosDiv = document.getElementById('eventosEspecificos');
    const errorMessageP = document.getElementById('errorMessage');
    const errorDetailsP = document.getElementById('errorDetails');

    // Define a data padrão como "amanhã"
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);
    predictionDateInput.value = tomorrow.toISOString().split('T')[0]; // Formato YYYY-MM-DD

    fetchDataButton.addEventListener('click', async () => {
        const selectedDate = predictionDateInput.value;
        if (!selectedDate) {
            alert('Por favor, selecione uma data para a previsão.');
            return;
        }

        // Esconde tudo e mostra o carregamento
        predictionResultsSection.classList.add('hidden');
        errorDisplaySection.classList.add('hidden');
        loadingSection.classList.remove('hidden');

        try {
            // CORRIGIDO: URL do backend para a URL do Render e `snake_case` para os parâmetros da URL
            const response = await fetch(`https://ia-previsao-ritmo-backend.onrender.com/predict?date=${selectedDate}`);
            const data = await response.json();

            if (!response.ok) {
                errorMessageP.textContent = data.error || "Erro desconhecido na previsão.";
                // CORRIGIDO: Nomes das chaves JSON para `snake_case` no erro
                errorDetailsP.textContent = `Data solicitada: ${data.requested_date || 'N/A'}, Período da Previsão: ${data.forecast_period_start || 'N/A'} a ${data.forecast_period_end || 'N/A'}.`;
                errorDisplaySection.classList.remove('hidden');
                loadingSection.classList.add('hidden');
                return;
            }

            // Popula os resultados
            dataPrevisaoSpan.textContent = data.data_previsao;
            // CORRIGIDO: Nome da chave JSON para `snake_case`
            if (data.previsao_total_yhat1 !== null && data.previsao_total_yhat1 !== undefined) {
                totalPrevistoHojeP.textContent = data.previsao_total_yhat1.toFixed(2); // Não adicionamos '%' aqui pois é o total de eventos previstos, não probabilidade
            } else {
                totalPrevistoHojeP.textContent = "N/A";
            }

            // Top 10 Motoristas Geral
            top10MotoristasGeralUl.innerHTML = '';
            // CORRIGIDO: Nome da chave JSON para `snake_case`
            if (data.top10_motoristas_geral && data.top10_motoristas_geral.length > 0) {
                data.top10_motoristas_geral.forEach(motorista => {
                    const li = document.createElement('li');
                    const probabilidade = motorista.Probabilidade;
                    // ALTERADO: Adicionado .replace('.', ',') e '%'
                    li.textContent = `${motorista.Motorista}: ${probabilidade !== null && probabilidade !== undefined ? probabilidade.toFixed(2).replace('.', ',') + '%' : 'N/A'}`;
                    top10MotoristasGeralUl.appendChild(li);
                });
            } else {
                top10MotoristasGeralUl.innerHTML = 'Nenhum motorista encontrado no top 10.';
            }

            // Probabilidade por Tipo de Evento
            eventosEspecificosDiv.innerHTML = '';
            // CORRIGIDO: Nome da chave JSON para `snake_case`
            if (data.probabilidade_eventos_especificos) {
                // CORRIGIDO: Iteração sobre a chave snake_case
                for (const evento in data.probabilidade_eventos_especificos) {
                    const eventCard = document.createElement('div');
                    eventCard.classList.add('result-card');
                    eventCard.innerHTML = `<h3>${evento}</h3>`;
                    const ul = document.createElement('ul');

                    // CORRIGIDO: Iteração sobre a chave snake_case
                    const eventoData = data.probabilidade_eventos_especificos[evento];
                    if (Array.isArray(eventoData) && eventoData.length > 0) {
                        eventoData.forEach(motorista => {
                            const li = document.createElement('li');
                            const probabilidade = motorista.Probabilidade;
                            // ALTERADO: Adicionado .replace('.', ',') e '%'
                            li.textContent = `${motorista.Motorista}: ${probabilidade !== null && probabilidade !== undefined ? probabilidade.toFixed(2).replace('.', ',') + '%' : 'N/A'}`;
                            ul.appendChild(li);
                        });
                    } else if (eventoData.message) {
                        ul.innerHTML = `<li>${eventoData.message}</li>`; // Adicionado <li> para consistência
                    } else if (eventoData.error) {
                        ul.innerHTML = `<li>Erro: ${eventoData.error}</li>`; // Adicionado <li> para consistência
                    } else {
                        ul.innerHTML = `<li>Nenhum dado detalhado encontrado para este evento.</li>`; // Adicionado <li> para consistência
                    }
                    eventCard.appendChild(ul);
                    eventosEspecificosDiv.appendChild(eventCard);
                }
            } else {
                eventosEspecificosDiv.innerHTML = 'Nenhuma probabilidade por tipo de evento disponível.';
            }

            // Mostra os resultados
            loadingSection.classList.add('hidden');
            predictionResultsSection.classList.remove('hidden');

        } catch (error) {
            console.error('Erro ao buscar dados:', error);
            errorMessageP.textContent = 'Não foi possível conectar ao servidor de previsão.';
            errorDetailsP.textContent = 'Certifique-se de que o backend está em execução e a URL no frontend está correta.';
            errorDisplaySection.classList.remove('hidden');
            loadingSection.classList.add('hidden');
        }
    });

    // Dispara o botão uma vez ao carregar a página para mostrar a previsão de amanhã
    fetchDataButton.click();
});