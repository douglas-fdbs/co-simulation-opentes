import itertools
import math
import mosaik_api

import simulators.pv_model as pvpanel

meta = {
    'type': 'hybrid',
    'models': {
        'PV': {
            'public': True,
            'params': [
                'lat',          # latitude of data measurement location [°]
                'area',         # area of panel [m2]
                'efficiency',   # panel efficiency
                'el_tilt',      # panel elevation tilt [°]
                'az_tilt',      # panel azimuth tilt [°]
            ],
            'attrs': ['P_gen',      # output active power [W]
                      'DNI',    # input direct normal insolation [W/m2]
                      'mod'],    # input of modifier from ctrl
            'trigger': ['DNI', 'mod']
        },
    },
}

DATE_FORMAT = 'YYYY-MM-DD HH:mm:ss'


class PvAdapter(mosaik_api.Simulator):
    def __init__(self):
        super(PvAdapter, self).__init__(meta)
        self.sid = None

        self.gen_neg = True     # true if generation is negative
        self.cache = None

        self._entities = {}
        self.mods = {}
        self.eid_counters = {}

    def init(self, sid, time_resolution, start_date, step_size=None, gen_neg=True):
        self.sid = sid
        self.gen_neg = gen_neg

        self.start_date = start_date
        self.step_size = step_size
        self.last_step = -1
        self.next_self_step = 0

        return self.meta

    def create(self, num, model, **model_params):
        counter = self.eid_counters.setdefault(model, itertools.count())

        entities = []

        # creation of the entities:
        for i in range(num):
            eid = '%s_%s' % (model, next(counter))

            self._entities[eid] = pvpanel.PVpanel(start_date=self.start_date,
                                                  **model_params)
            self.mods[eid] = 1.

            entities.append({'eid': eid, 'type': model, 'rel': []})

        return entities

    def step(self, t, inputs, max_advance):
        # print('%s: %s: %s' % (t, max_advance, inputs))


        self.cache = {}
        for eid, attrs in inputs.items():
            if t != self.last_step:
                fac = math.exp(-(t-self.last_step)/900.)  # Relax mod towards 1 within 15min
                self.mods[eid] = 1. - fac + fac*self.mods[eid]
                #print('valor de fac no primeiro IF',fac)
            if 'mod' in attrs:
                vals = attrs.get('mod')
                mod = list(vals.values())[0]
                #mod = 1
                self.mods[eid] *= mod
                print('PV-Controller Signal at time', t, 'is', mod)
                #print('valor de fac no segundo IF',fac)
            for attr, vals in attrs.items():
                if attr == 'DNI':
                    dni = list(vals.values())[0] # only one source expected
                    self.cache[eid] = self._entities[eid].power(dni)
                    if t != self.last_step:
                        self._entities[eid].step_time(t - self.last_step)
                    if self.gen_neg:
                        self.cache[eid] *= (-1)
                #print('valor de fac no loop for',fac)
            self.cache[eid] *= self.mods[eid]

        self.last_step = t

        if self.step_size and t == self.next_self_step:
            next_step = t + self.step_size
            self.next_self_step = next_step
        else:
            next_step = None
        return next_step

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            if eid not in self._entities.keys():
                raise ValueError('Unknown entity ID "%s"' % eid)

            data[eid] = {}
            for attr in attrs:
                #if attr != 'P_gen':
                #    raise ValueError('Unknown output attribute "%s"' % attr)
                if attr == 'P_gen':
                    data[eid][attr] = self.cache[eid]
                elif attr == 'mod':
                    data[eid][attr] = self.mods[eid]

        return data


def main():
    mosaik_api.start_simulation(PvAdapter(), 'PV-Simulator')
