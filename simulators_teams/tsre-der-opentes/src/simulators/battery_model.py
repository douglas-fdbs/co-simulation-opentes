import math

class OpenDSSBattery: 
    """
    Implementação Python fiel ao modelo 'Storage' do OpenDSS (Storage.pas).
    
    Convenção de Sinais (Gerador/OpenDSS):
    - kW > 0: Discharging (Injetando na rede)
    - kW < 0: Charging (Absorvendo da rede)
    """
    
    STATE_IDLING = 0
    STATE_DISCHARGING = 1
    STATE_CHARGING = -1

    def __init__(self, name, 
                 kw_rated, 
                 kwh_rated, 
                 kwh_stored, 
                 pct_reserve=20.0,
                 pct_eff_charge=90.0, 
                 pct_eff_discharge=90.0, 
                 pct_idling_kw=2.0,
                 kva_rated=None,
                 max_charge_kw=None,
                 max_discharge_kw=None,
                 eff_curve_x=[0.1, 0.2, 0.4, 1.0],
                 eff_curve_y=[0.86, 0.9, 0.93, 0.97]):
        
        self.name = name
        
        # Curva de Eficiência do Inversor (Seguro contra vazamento de memória)
        self.eff_curve_x = eff_curve_x if eff_curve_x is not None else [0.1, 0.2, 0.4, 1.0]
        self.eff_curve_y = eff_curve_y if eff_curve_y is not None else [0.86, 0.9, 0.93, 0.97]

        # Parâmetros Nominais
        self.kw_rated = float(kw_rated)
        self.kwh_rated = float(kwh_rated)
        self.kwh_reserve = float(pct_reserve / 100.0) * self.kwh_rated # Nível mínimo antes de parar descarga
        
        # # Estado InicialP --------------------------
        self.kwh_stored = float(kwh_stored)
        self.state = self.STATE_IDLING
        
        # Eficiências e Perdas
        self.eff_charge = float(pct_eff_charge/100)
        self.eff_discharge = float(pct_eff_discharge/100)
        self.pct_idling_kw = float(pct_idling_kw)
        self.idling_kw = (self.pct_idling_kw / 100.0) * self.kw_rated
        
        # Curva de Eficiência do Inversor
        self.eff_curve_x = eff_curve_x
        self.eff_curve_y = eff_curve_y

        # Limites do Inversor
        self.kva_rated = float(kva_rated) if kva_rated else self.kw_rated * 1.0 # Default PF=1
        
        # Limites explícitos de carga/descarga (se diferentes do nominal)
        self.max_charge_kw = max_charge_kw if max_charge_kw else self.kw_rated
        self.max_discharge_kw = max_discharge_kw if max_discharge_kw else self.kw_rated

        # Variáveis de Estado de Tempo Discreto
        self.kwh_stored = float(kwh_stored)
        self.pending_delta_energy = 0.0
        self.state = self.STATE_IDLING


        # Saídas iniciais
        eta_inv_idle = self.get_inverter_efficiency(self.idling_kw)
        self.p_out_kw = -(self.idling_kw / eta_inv_idle) if eta_inv_idle > 0 else -self.idling_kw
        self.q_out_kvar = 0.0

    def calculate_step(self, p_request, q_request, dt_seconds):
        """
        Executa a lógica de despacho e atualização de estado para um passo de tempo.
        
        Args:
            p_request (float): Potência ativa solicitada (+ Descarrega, - Carrega)
            q_request (float): Potência reativa solicitada
            dt_hours (float): Passo de tempo em horas
            
        Returns:
            dict: Estado atualizado e potências efetivas.
        """

        dt_hours = dt_seconds / 3600.0
        
        # ------------------------------------------------------------------
        # 1. Limitação pelo Inversor (Círculo de Potência Aparente)
        # ------------------------------------------------------------------

        p_limited = float(p_request) if p_request is not None else 0.0
        q_limited = float(q_request) if q_request is not None else 0.0
        
        self.kwh_stored += self.pending_delta_energy

        # Clamp P nos limites nominais de carga/descarga
        if p_limited > self.max_discharge_kw:
            p_limited = self.max_discharge_kw
        elif p_limited < -self.max_charge_kw:
            p_limited = -self.max_charge_kw
            
        # Verifica violação de kVA
        s_sq = p_limited**2 + q_limited**2
        if s_sq > self.kva_rated**2:
            # Se exceder kVA, reduz Q primeiro (Prioridade P)
            available_q = math.sqrt(max(0, self.kva_rated**2 - p_limited**2))
            if q_limited > 0:
                q_limited = available_q
            else:
                q_limited = -available_q
                
            # Se mesmo com Q=0 o P for muito alto (raro se kw_rated <= kva_rated), clamp P
            if abs(p_limited) > self.kva_rated:
                 p_limited = math.copysign(self.kva_rated, p_limited)

        # ------------------------------------------------------------------
        # 2. DEFINIÇÃO DO COMPORTAMENTO PADRÃO (FALLBACK)
        # ------------------------------------------------------------------
        calc_delta_energy = 0.0
        next_state = self.STATE_IDLING

        eta_inv_idle = self.get_inverter_efficiency(self.idling_kw)
        
        # Guardamos essa variável para usá-la na Média Ponderada
        p_idle_ac = -(self.idling_kw / eta_inv_idle) if eta_inv_idle > 0 else -self.idling_kw
        p_output = p_idle_ac

        # ------------------------------------------------------------------
        # 3. Determinação do Estado e Cálculo da Energia Química (Lado DC)
        # Emulação do Fotógrafo (Instantâneo) OpenDSS
        # ------------------------------------------------------------------
        if p_limited > 1e-6:
            # --- TENTATIVA DE DESCARGA (Injetar na rede) ---
            eta_inv = self.get_inverter_efficiency(p_limited)
            if eta_inv > 0:
                p_dc_req = p_limited / eta_inv             
                p_chem = p_dc_req / self.eff_discharge   
                
                total_drain_rate = p_chem + self.idling_kw     
                
                energy_required = total_drain_rate * dt_hours
                available_energy = max(0.0, self.kwh_stored - self.kwh_reserve)
                
                if available_energy > 0:
                    # Trava a potência lida no valor nominal (foto instantânea)
                    next_state = self.STATE_DISCHARGING
                    p_output = p_limited
                    
                    if energy_required > available_energy:
                        # Bateria esvazia no meio do passo: limita apenas a energia
                        calc_delta_energy = -available_energy
                    else:
                        calc_delta_energy = -energy_required

        elif p_limited < -1e-6:
            # --- TENTATIVA DE CARGA (Absorver da rede) ---
            p_grid_mag = abs(p_limited)
            eta_inv = self.get_inverter_efficiency(p_grid_mag)
            
            p_dc_input = p_grid_mag * eta_inv              
            p_chem = p_dc_input * self.eff_charge            
            
            total_charge_rate = p_chem - self.idling_kw

            if total_charge_rate > 0:
                energy_space = max(0.0, self.kwh_rated - self.kwh_stored)
                energy_to_store = total_charge_rate * dt_hours
                
                if energy_space > 0:
                    # Trava a potência lida no valor nominal (foto instantânea)
                    next_state = self.STATE_CHARGING
                    p_output = p_limited
                    
                    if energy_to_store > energy_space:
                        # Bateria enche no meio do passo: limita apenas o espaço
                        calc_delta_energy = energy_space
                    else:
                        calc_delta_energy = energy_to_store

        # ------------------------------------------------------------------
        # 4. Atualização Final do Estado
        # ------------------------------------------------------------------

        # Clamp de segurança (erros numéricos)
        if self.kwh_stored < 0: self.kwh_stored = 0.0
        if self.kwh_stored > self.kwh_rated: self.kwh_stored = self.kwh_rated

        self.pending_delta_energy = calc_delta_energy    
        self.state = next_state
        self.p_out_kw = p_output
        self.q_out_kvar = q_limited

        return {
            'p_kw': self.p_out_kw,
            'q_kvar': self.q_out_kvar,
            'soc_pct': (self.kwh_stored / self.kwh_rated) * 100,
            'state': self.get_state_str()
        }

    def get_state_str(self):
        if self.state == self.STATE_CHARGING: return "Charging"
        if self.state == self.STATE_DISCHARGING: return "Discharging"
        return "Idling"
    
    def get_inverter_efficiency(self, p_kw):
        """Interpola ou Extrapola linearmente a eficiência baseada na curva XY do OpenDSS."""
        p_pu = abs(p_kw) / self.kw_rated if self.kw_rated > 0 else 0.0
        
        if p_pu <= 0.0: 
            return 0.0
            
        # Trava no limite superior se passar do máximo da curva (ex: 1.0 pu)
        if p_pu >= self.eff_curve_x[-1]: 
            return self.eff_curve_y[-1]
        
        # Interpolação e Extrapolação Linear (para baixo)
        for i in range(len(self.eff_curve_x) - 1):
            if p_pu <= self.eff_curve_x[i+1]:
                x0, x1 = self.eff_curve_x[i], self.eff_curve_x[i+1]
                y0, y1 = self.eff_curve_y[i], self.eff_curve_y[i+1]
                eta = y0 + (p_pu - x0) * (y1 - y0) / (x1 - x0)
                return max(0.1, eta) # Limite de segurança matemático para não dividir por 0
                
        return 0.0