library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library unisim;
use unisim.vcomponents.all;

use work.camera_pkg.all;

entity camera_wrapper is
    generic (
        SYNC_INVERTED  : boolean;
        DATA3_INVERTED : boolean;
        DATA2_INVERTED : boolean;
        DATA1_INVERTED : boolean;
        DATA0_INVERTED : boolean);
    port (
        clock_camera_unbuf  : in std_logic;
        clock_camera_over_2 : in std_logic;
        clock_camera_over_5 : in std_logic;
        clock_locked        : in std_logic;
        reset               : in std_logic;
        
        camera_out : out camera_out;
        camera_in  : in  camera_in;
        
        output : out camera_output);
end camera_wrapper;

architecture arc of camera_wrapper is
    signal clock_out : std_logic;
    
    signal deserializer_clock : std_logic;
    
    subtype BitslipType is integer range 0 to 9;
    signal bitslip_sync : BitslipType;
    type BitslipDataType is array (0 to 3) of BitslipType;
    signal bitslip_data : BitslipDataType;
    
    type DataArray is array (0 to 3) of unsigned(9 downto 0);
    signal sync_maybe_inv : unsigned(9 downto 0);
    signal data_maybe_inv : DataArray;
    
    signal deserializer_out : std_logic_vector(24 downto 0);
    signal sync_maybe_inv_s, sync_s : unsigned(9 downto 0);
    signal odd_s, sync_is_window_id_s : boolean;
begin
    CLOCK_OUT_DDR : ODDR2
        generic map (
            DDR_ALIGNMENT => "NONE",
            INIT          => '0',
            SRTYPE        => "SYNC")
        port map (
            Q  => clock_out,
            C0 => clock_camera_over_2,
            C1 => not clock_camera_over_2,
            CE => '1',
            D0 => '1',
            D1 => '0',
            R  => '0',
            S  => '0');
    CLOCK_OUT_OBUF : OBUFDS
        generic map (
            IOSTANDARD => "LVDS_33")
        port map (
            I  => clock_out,
            O  => camera_out.clock_p,
            OB => camera_out.clock_n);
    
    deserializer_clock <= clock_camera_over_5;
    DESERIALIZER : entity work.camera_deserializer port map (
        IO_RESET => reset,
        
        CLK_IN => clock_camera_unbuf,
        CLK_DIV_IN => clock_camera_over_5,
        LOCKED_IN => clock_locked,
        DATA_IN_FROM_PINS_P => camera_in.sync_p & camera_in.data3_p &
            camera_in.data2_p & camera_in.data1_p & camera_in.data0_p,
        DATA_IN_FROM_PINS_N => camera_in.sync_n & camera_in.data3_n &
            camera_in.data2_n & camera_in.data1_n & camera_in.data0_n,
        
        LOCKED_OUT => open,
        DATA_IN_TO_DEVICE => deserializer_out,
        BITSLIP => (others => '0'),
        
        DEBUG_IN => "00",
        DEBUG_OUT => open);
    
    process (deserializer_clock) is
        variable sync_buf : unsigned(27 downto 0);
        type DataBufArray is array (0 to 3) of unsigned(27 downto 0);
        variable data_buf : DataBufArray;
        
        variable sync_buf2 : unsigned(18 downto 0);
        type DataBuf2Array is array (0 to 3) of unsigned(18 downto 0);
        variable data_buf2 : DataBuf2Array;
    begin
        if rising_edge(deserializer_clock) then
            sync_maybe_inv <= sync_buf2(14 downto 5);
            for j in 0 to 3 loop
                data_maybe_inv(j) <= data_buf2(j)(bitslip_data(j)+9 downto bitslip_data(j));
            end loop;
            
            sync_buf2 := sync_buf(bitslip_sync+18 downto bitslip_sync);
            for j in 0 to 3 loop
                data_buf2(j) := data_buf(j)(bitslip_sync+18 downto bitslip_sync);
            end loop;
            
            sync_buf(sync_buf'high downto 5) := sync_buf(sync_buf'high-5 downto 0);
            for j in 0 to 3 loop
                data_buf(j)(data_buf(j)'high downto 5) := data_buf(j)(data_buf(j)'high-5 downto 0);
            end loop;
            -- fill sync_buf and data_buf with deserializer_out
            for i in 0 to 4 loop
                sync_buf(4-i) := deserializer_out(4+5*i);
                for j in 0 to 3 loop
                    data_buf(j)(4-i) := deserializer_out(j+5*i);
                end loop;
            end loop;
        end if;
    end process;
    
    output.clock <= deserializer_clock;
    process (deserializer_clock) is
        variable bitslip_countdown : integer range 0 to 5;
        variable odd : boolean;
        variable sync : unsigned(9 downto 0);
        variable data : DataArray;
        variable data_valid, sync_is_window_id : boolean;
        variable line_end, frame_end : boolean;
        variable kernel_pos, last_kernel_pos : integer range 0 to 3;
        variable kernel_read_pos : integer range 0 to 4 := 0;
        type Kernel is array (0 to 7) of unsigned(9 downto 0);
        variable even_kernel : Kernel;
        variable even_kernel_line_end, even_kernel_frame_end : boolean;
        variable odd_kernel : Kernel;
        variable odd_kernel_line_end, odd_kernel_frame_end : boolean;
        variable in_frame : boolean;
    begin
        if rising_edge(deserializer_clock) then
            if bitslip_countdown /= 0 then
                bitslip_countdown := bitslip_countdown - 1;
            end if;
            
            output.data_valid <= '0';
            output.last_column <= '0';
            output.last_pixel <= '0';
            if kernel_read_pos = 0 then
                if last_kernel_pos = 1 then
                    if odd then
                        output.data_valid <= '1';
                        output.pixel1 <= even_kernel(0);
                        output.pixel2 <= even_kernel(1);
                    else
                        output.data_valid <= '1';
                        output.pixel1 <= even_kernel(2);
                        output.pixel2 <= even_kernel(3);
                        kernel_read_pos := 1;
                    end if;
                end if;
            elsif kernel_read_pos = 1 then
                if odd then
                    output.data_valid <= '1';
                    output.pixel1 <= even_kernel(4);
                    output.pixel2 <= even_kernel(5);
                else
                    output.data_valid <= '1';
                    output.pixel1 <= even_kernel(6);
                    output.pixel2 <= even_kernel(7);
                    kernel_read_pos := 2;
                    if even_kernel_line_end then
                        output.last_column <= '1';
                        if last_kernel_pos = 1 then
                            kernel_read_pos := 4;
                        else
                            kernel_read_pos := 0;
                        end if;
                    end if;
                    if even_kernel_frame_end then
                        output.last_pixel <= '1';
                    end if;
                end if;
            elsif kernel_read_pos = 2 then
                if last_kernel_pos = 3 then
                    if odd then
                        output.data_valid <= '1';
                        output.pixel1 <= odd_kernel(0);
                        output.pixel2 <= odd_kernel(1);
                    else
                        output.data_valid <= '1';
                        output.pixel1 <= odd_kernel(2);
                        output.pixel2 <= odd_kernel(3);
                        kernel_read_pos := 3;
                    end if;
                end if;
            elsif kernel_read_pos = 3 then
                if odd then
                    output.data_valid <= '1';
                    output.pixel1 <= odd_kernel(4);
                    output.pixel2 <= odd_kernel(5);
                else
                    output.data_valid <= '1';
                    output.pixel1 <= odd_kernel(6);
                    output.pixel2 <= odd_kernel(7);
                    kernel_read_pos := 0;
                    if odd_kernel_line_end then
                        output.last_column <= '1';
                        kernel_read_pos := 0;
                    end if;
                    if odd_kernel_frame_end then
                        output.last_pixel <= '1';
                    end if;
                end if;
            elsif kernel_read_pos = 4 then
                if last_kernel_pos /= 1 then
                    kernel_read_pos := 0;
                end if;
            end if;
            
            if not odd then -- sync_maybe_inv and data_maybe_inv are valid
                -- process sync_maybe_inv and data_maybe_inv into sync and data
                if SYNC_INVERTED then sync := not sync_maybe_inv; else sync := sync_maybe_inv; end if;
                if DATA3_INVERTED then data(3) := not data_maybe_inv(3); else data(3) := data_maybe_inv(3); end if;
                if DATA2_INVERTED then data(2) := not data_maybe_inv(2); else data(2) := data_maybe_inv(2); end if;
                if DATA1_INVERTED then data(1) := not data_maybe_inv(1); else data(1) := data_maybe_inv(1); end if;
                if DATA0_INVERTED then data(0) := not data_maybe_inv(0); else data(0) := data_maybe_inv(0); end if;
                
                -- process sync, data
                
                data_valid := false;
                line_end := false;
                frame_end := false;
                if sync_is_window_id then
                    sync_is_window_id := false;
                    data_valid := true;
                elsif sync = to_unsigned(16#5#, 3) & to_unsigned(16#2A#, 7) then -- frame start
                    data_valid := true;
                    sync_is_window_id := true;
                    kernel_pos := 0;
                    last_kernel_pos := 0;
                    in_frame := true;
                elsif sync = to_unsigned(16#6#, 3) & to_unsigned(16#2A#, 7) then -- frame end
                    data_valid := true;
                    sync_is_window_id := true;
                    line_end := true;
                    frame_end := true;
                    in_frame := false;
                elsif sync = to_unsigned(16#1#, 3) & to_unsigned(16#2A#, 7) then -- line start
                    sync_is_window_id := true;
                    if in_frame then
                        data_valid := true;
                        kernel_pos := 0;
                        last_kernel_pos := 0;
                    end if;
                elsif sync = to_unsigned(16#2#, 3) & to_unsigned(16#2A#, 7) then -- line end
                    sync_is_window_id := true;
                    if in_frame then
                        data_valid := true;
                        line_end := true;
                    end if;
                elsif sync = to_unsigned(16#015#, 10) then -- black
                elsif sync = to_unsigned(16#035#, 10) then -- valid
                    data_valid := true;
                elsif sync = to_unsigned(16#059#, 10) then -- CRC
                elsif sync = to_unsigned(16#3A6#, 10) then -- train
                    for i in 0 to 3 loop
                        if data(i) /= to_unsigned(16#3A6#, 10) then
                            if bitslip_countdown = 0 then
                                if bitslip_data(i) /= 9 then
                                    bitslip_data(i) <= bitslip_data(i) + 1;
                                else
                                    bitslip_data(i) <= 0;
                                end if;
                                bitslip_countdown := 5;
                            end if;
                        end if;
                    end loop;
                else
                    if bitslip_countdown = 0 then
                        if bitslip_sync /= 9 then
                            bitslip_sync <= bitslip_sync + 1;
                        else
                            bitslip_sync <= 0;
                        end if;
                        bitslip_countdown := 5;
                    end if;
                end if;
                
                last_kernel_pos := kernel_pos;
                if data_valid then
                    if kernel_pos = 0 then
                        even_kernel(0) := data(0);
                        even_kernel(2) := data(1);
                        even_kernel(4) := data(2);
                        even_kernel(6) := data(3);
                        even_kernel_line_end := line_end;
                        even_kernel_frame_end := frame_end;
                        kernel_pos := 1;
                    elsif kernel_pos = 1 then
                        even_kernel(1) := data(0);
                        even_kernel(3) := data(1);
                        even_kernel(5) := data(2);
                        even_kernel(7) := data(3);
                        kernel_pos := 2;
                    elsif kernel_pos = 2 then
                        odd_kernel (7) := data(0);
                        odd_kernel (5) := data(1);
                        odd_kernel (3) := data(2);
                        odd_kernel (1) := data(3);
                        odd_kernel_line_end := line_end;
                        odd_kernel_frame_end := frame_end;
                        kernel_pos := 3;
                    elsif kernel_pos = 3 then
                        odd_kernel (6) := data(0);
                        odd_kernel (4) := data(1);
                        odd_kernel (2) := data(2);
                        odd_kernel (0) := data(3);
                        kernel_pos := 0;
                    end if;
                end if;
            end if;
            
            
            odd := not odd;
            
            sync_s <= sync;
            sync_maybe_inv_s <= sync_maybe_inv;
            odd_s <= odd;
            sync_is_window_id_s <= sync_is_window_id;
        end if;
    end process;
end architecture;
