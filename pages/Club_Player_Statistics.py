
import bridgestats

if __name__ == '__main__':
    chart_options = ['ParScore','ContractType','Declarer_Pct','DD_Tricks','DD_Score_Declarer','MP_DD_Pct_Declarer','Tricks_DD_Diff','Score_Declarer_DD_Diff','ParScore_DD_Diff']
    club_or_tournament = 'club'
    pair_or_player = 'player'
    groupby=['Declarer','Dummy']
    bridgestats.Stats(club_or_tournament, pair_or_player, chart_options, groupby)
