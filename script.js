document.addEventListener('DOMContentLoaded', () => {

  // ========== Seção de Previsão ==========
  const dateInput = document.getElementById('dateInput');
  const dateForm = document.getElementById('dateForm');
  const resultadoSection = document.getElementById('resultado');
  const dataPrevisaoSpan = document.getElementById('dataPrevisao');
  const previsaoQtdSpan = document.getElementById('previsaoQtd');
  const top10MotoristasOl = document.getElementById('top10Motoristas');
  const eventosEspecificosDiv = document.getElementById('eventosEspecificos');
  const top5LocaisOl = document.getElementById('top5Locais'); // <-- NEW: Elemento para os locais
  const mensagemErro = document.getElementById('mensagemErro');

  // Define a data padrão como amanhã
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);
  dateInput.value = tomorrow.toISOString().split('T')[0];

  async function buscarPrevisao(dateString) {
    // Limpa e exibe loading
    resultadoSection.style.display = 'none';
    mensagemErro.style.display = 'none';
    previsaoQtdSpan.textContent = '';
    dataPrevisaoSpan.textContent = '';
    top10MotoristasOl.innerHTML = '';
    eventosEspecificosDiv.innerHTML = '';
    top5LocaisOl.innerHTML = ''; // <-- NEW: Limpa a lista de locais

    try {
      // Troque aqui a URL para a do seu backend, se necessário
      const response = await fetch(`https://ia-previsao-ritmo-backend.onrender.com/predict?date=${dateString}`);
      const data = await response.json();

      if (!response.ok) {
        mensagemErro.textContent = data.error || 'Erro desconhecido na previsão.';
        mensagemErro.style.display = 'block';
        return;
      }

      // Data de Previsão e Previsão Total
      dataPrevisaoSpan.textContent = data.data_previsao || 'N/A';
      if (data.previsaototalyhat1 !== null && data.previsaototalyhat1 !== undefined) {
        previsaoQtdSpan.textContent = data.previsaototalyhat1.toFixed(2);
      } else {
        previsaoQtdSpan.textContent = 'N/A';
      }

      // Top 10 Motoristas Geral (novo estilo)
      top10MotoristasOl.innerHTML = '';
      if (data.top10motoristasgeral && data.top10motoristasgeral.length > 0) {
        data.top10motoristasgeral.forEach((motorista) => {
          const li = document.createElement('li');
          const probabilidade = motorista.Probabilidade !== null && motorista.Probabilidade !== undefined ? motorista.Probabilidade.toFixed(2).replace('.', ',') + '%' : 'N/A';
          li.innerHTML = `<span>${motorista.Motorista}</span> <span class="valor">${probabilidade}</span>`;
          top10MotoristasOl.appendChild(li);
        });
      } else {
        top10MotoristasOl.innerHTML = '<li>Nenhum motorista encontrado no top 10.</li>';
      }

      // Probabilidades por Tipo de Evento
      eventosEspecificosDiv.innerHTML = '';
      if (data.probabilidadeeventosespecificos) {
        for (const evento in data.probabilidadeeventosespecificos) {
          const eventCard = document.createElement('div');
          eventCard.classList.add('result-card');
          const titulo = document.createElement('strong');
          titulo.textContent = evento;
          eventCard.appendChild(titulo);

          const ul = document.createElement('ul');
          const eventoData = data.probabilidadeeventosespecificos[evento];
          if (Array.isArray(eventoData) && eventoData.length > 0) {
            eventoData.forEach(motorista => {
              const li = document.createElement('li');
              const probabilidade = motorista.Probabilidade;
              li.textContent = `${motorista.Motorista}: ${probabilidade !== null && probabilidade !== undefined ? probabilidade.toFixed(2).replace('.', ',') + '%' : 'N/A'}`;
              ul.appendChild(li);
            });
          } else if (eventoData && eventoData.message) {
            ul.innerHTML = `<li>${eventoData.message}</li>`;
          } else if (eventoData && eventoData.error) {
            ul.innerHTML = `<li>Erro: ${eventoData.error}</li>`;
          } else {
            ul.innerHTML = `<li>Nenhum dado detalhado encontrado para este evento.</li>`;
          }
          eventCard.appendChild(ul);
          eventosEspecificosDiv.appendChild(eventCard);
        }
      } else {
        eventosEspecificosDiv.innerHTML = 'Nenhuma probabilidade por tipo de evento disponível.';
      }

      // NEW: Top 5 Locais de Maior Probabilidade
      top5LocaisOl.innerHTML = ''; // Garante que esteja limpo antes de preencher
      if (data.top5localidades && data.top5localidades.length > 0) {
        data.top5localidades.forEach((local) => {
          const li = document.createElement('li');
          // Verifica se é uma mensagem de erro/informação ou dados reais
          if (local.message) {
              li.textContent = local.message;
          } else {
              const probabilidade = local.Probabilidade !== null && local.Probabilidade !== undefined ? local.Probabilidade.toFixed(2).replace('.', ',') + '%' : 'N/A';
              li.innerHTML = `<span>${local.Localidade}</span> <span class="valor">${probabilidade}</span>`;
          }
          top5LocaisOl.appendChild(li);
        });
      } else {
        top5LocaisOl.innerHTML = '<li>Nenhum local encontrado para o top 5.</li>';
      }


      // Exibe resultados
      resultadoSection.style.display = 'block';

    } catch (error) {
      mensagemErro.textContent = 'Não foi possível conectar ao servidor de previsão. Verifique a URL do backend ou se o serviço está online.';
      mensagemErro.style.display = 'block';
      console.error("Erro ao buscar previsão:", error);
    }
  }

  // Evento de envio do formulário de data
  dateForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const selectedDate = dateInput.value;
    if (!selectedDate) {
      alert('Selecione uma data!');
      return;
    }
    buscarPrevisao(selectedDate);
  });

  // Chama automaticamente para a previsão de amanhã ao carregar
  buscarPrevisao(dateInput.value);

  // ========== Seção de Upload de Arquivo ==========
  const uploadForm = document.getElementById('uploadForm');
  const csvFileInput = document.getElementById('csvFileInput');
  const uploadStatus = document.getElementById('uploadStatus');

  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!csvFileInput.files.length) {
      alert('Selecione um arquivo CSV.');
      return;
    }
    const formData = new FormData();
    formData.append('file', csvFileInput.files[0]);

    uploadStatus.textContent = 'Enviando arquivo...';

    try {
      const response = await fetch('https://ia-previsao-ritmo-backend.onrender.com/upload_csv', {
        method: 'POST',
        body: formData
      });
      const result = await response.json();

      if (response.ok) {
        uploadStatus.textContent = result.message || 'Arquivo enviado com sucesso!';
        uploadStatus.style.color = 'green';
        // Sugestão: Buscar de novo a previsão para atualizar com a nova base já carregada!
        buscarPrevisao(dateInput.value);
      } else {
        uploadStatus.textContent = result.error || 'Erro ao enviar o arquivo.';
        uploadStatus.style.color = '#e74c3c';
      }
    } catch (err) {
      uploadStatus.textContent = 'Erro de conexão com o backend.';
      uploadStatus.style.color = '#e74c3c';
    }
  });
});