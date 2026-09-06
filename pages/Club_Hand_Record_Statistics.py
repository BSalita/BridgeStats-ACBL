
import handstats

if __name__ == '__main__':
    chart_options = ['ParScore','CT_N_S,CT_N_H,CT_N_D,CT_N_C,CT_N_N','DD_N_C,DD_N_D,DD_N_H,DD_N_S,DD_N_N']
    club_or_tournament = 'club'
    pair_or_player = None
    groupby = None
    handstats.Stats(club_or_tournament, pair_or_player, chart_options, groupby)
