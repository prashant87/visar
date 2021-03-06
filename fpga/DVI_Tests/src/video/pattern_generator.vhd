library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.video_bus.all;


entity video_pattern_generator is
    port (
        sync : in video_sync;
        
        data_out : out video_data);
end video_pattern_generator;

architecture Behavioral of video_pattern_generator is
    signal h_cnt : HCountType;
    signal v_cnt : VCountType;
begin
    u_counter : entity work.video_counter port map (
        sync => sync,
        h_cnt => h_cnt,
        v_cnt => v_cnt);

    process (h_cnt, v_cnt) is
    begin
        data_out.red   <= x"00";
        data_out.green <= x"00";
        data_out.blue  <= x"00";
    end process;
end Behavioral;
