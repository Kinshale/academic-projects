----------------------------------------------------------------------------------
-- Company: 
-- Engineer: 
-- 
-- Create Date: 07/04/2025 01:16:51 PM
-- Design Name: 
-- Module Name: differential-filter - Behavioral
-- Project Name: 
-- Target Devices: 
-- Tool Versions: 
-- Description: 
-- 
-- Dependencies: 
-- 
-- Revision:
-- Revision 0.01 - File Created
-- Additional Comments:
-- 
----------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.textio.all;

entity project_reti_logiche is
port (
    i_clk      : in  std_logic;
    i_rst      : in  std_logic;
    i_start    : in  std_logic;
    i_add      : in  std_logic_vector(15 downto 0);

    o_done     : out std_logic;

    o_mem_addr : out std_logic_vector(15 downto 0);
    i_mem_data : in  std_logic_vector(7 downto 0);
    o_mem_data : out std_logic_vector(7 downto 0);
    o_mem_we   : out std_logic;
    o_mem_en   : out std_logic
);
end project_reti_logiche;

architecture Behavioral of project_reti_logiche is

    type state_type is (
        IDLE,           -- Waiting for start signal
        READ_HEADER,    -- Read K1,K2,S,C1-C14 from memory and put them in registers
        READ_HD_WAIT,
        INIT_WINDOW,    -- Initialize the sliding window, which contains the inputs
        INIT_WAIT, 
        APPLY_FILTER,   -- Perform the convolution
        NORMALIZE_RESULT,
        SATURATE_RESULT,
        WRITE_OUTPUT,  
        WRITE_WAIT,     -- Write happens on the next rising edge
        SLIDE_WINDOW,   -- Move the input window one forward
        SLIDE_WAIT,
        DONE_STATE    
    );

    type input_slide_type is array (0 to 6) of std_logic_vector(7 downto 0); -- Holds at max 7 bytes at a time

    signal current_state, next_state : state_type;

    signal K: unsigned(15 downto 0);
    signal S: std_logic_vector(7 downto 0);
    signal coefficients: std_logic_vector(111 downto 0); -- 14 bytes
    signal input_slide : input_slide_type;

    signal base_address : std_logic_vector(15 downto 0);

    signal header_counter : unsigned(4 downto 0); -- Counts header bytes read (0-16)
    signal init_counter : unsigned(2 downto 0);
    signal data_counter : unsigned(15 downto 0); -- Counter from 0 to K
    signal filter_counter : integer range 0 to 6; 

    signal filtered_value : signed(18 downto 0);  -- After convolution
    signal temp_result : signed(18 downto 0);     -- After normalization
    signal data_buffer : std_logic_vector(7 downto 0); -- After Saturation

    signal filter_order : integer range 0 to 1; -- 0 = order 3, 1 = order 5

begin

    -- State register process
    state_reg: process(i_clk, i_rst)

        -- NOTE: sum is now 2^19 bits, which is enough for -128 * -128 * 7 ~ 2^17 with the sign
        variable sum : signed(18 downto 0);
        variable normalized : signed(18 downto 0);
        variable coeff : signed(7 downto 0);
        variable coeff_index : integer;
        variable data_index : integer;
        variable current_input : signed(7 downto 0);

    begin
        if i_rst = '1' then

            -- When rst = 1, we reset all registers to 0
            current_state <= IDLE;

            base_address <= (others => '0');
            header_counter <= (others => '0');
            init_counter <= (others => '0');
            data_counter <= (others => '0');

            K <= (others => '0');
            S <= (others => '0');
            coefficients <= (others => '0');
            input_slide <= (others => (others => '0'));

            filter_order <= 0; --NOTE: Default is order 3
            filter_counter <= 0;

            filtered_value <= (others => '0');
            temp_result <= (others => '0');
            data_buffer <= (others => '0');

        -- On the rising edge we do stuff
        elsif rising_edge(i_clk) then
            current_state <= next_state;

            case current_state is
                when IDLE =>
                    if i_start = '1' then
                        base_address <= i_add;
                        header_counter <= (others => '0');
                    end if;

                when READ_HEADER =>
                    null;

                when READ_HD_WAIT =>
                    case to_integer(header_counter) is
                        when 0 => 
                            K(15 downto 8) <= unsigned(i_mem_data);
                        when 1 => 
                            K(7 downto 0) <= unsigned(i_mem_data);
                        when 2 => 
                            S <= i_mem_data;

                            if i_mem_data(0) = '0' then
                                filter_order <= 0; -- Order 3
                            else
                                filter_order <= 1; -- Order 5
                            end if;
                        when 3 to 16 => 
                            coefficients((to_integer(header_counter)-3)*8+7 downto (to_integer(header_counter)-3)*8) <= i_mem_data;
                        when others => null;
                    end case;

                    if header_counter < 16 then
                        header_counter <= header_counter + 1;
                    end if;

                when INIT_WINDOW =>
                    null;

                when INIT_WAIT =>
                        if S(0) = '0' then
                            case to_integer(init_counter) is
                                when 0 => 
                                    input_slide(2) <= i_mem_data;
                                when 1 =>
                                    input_slide(3) <= i_mem_data;
                                when 2 =>
                                    input_slide(4) <= i_mem_data;
                                when others => null;
                            end case;

                        else -- Order 5 filter
                            case to_integer(init_counter) is
                                when 0 => 
                                    input_slide(3) <= i_mem_data;
                                when 1 =>
                                    input_slide(4) <= i_mem_data;
                                when 2 =>
                                    input_slide(5) <= i_mem_data;
                                when 3 =>
                                    input_slide(6) <= i_mem_data;
                                when others => null;
                            end case;
                        end if;

                        -- WARN: Hardcoded, may be shortened

                        if init_counter < (2 + filter_order) then
                            init_counter <= init_counter + 1;
                        end if;

                when APPLY_FILTER =>
                    if filter_counter = 0 then
                        sum := (others => '0');
                    end if;

                    if S(0) = '0' then -- Order 3 (5 coefficients: C2-C6)
                        coeff_index := filter_counter + 1;
                    else -- Order 5 (7 coefficients: C8-C14)
                        coeff_index := filter_counter + 7;
                    end if;

                    coeff := signed(coefficients(coeff_index*8+7 downto coeff_index*8));

                    sum := sum + coeff * signed(input_slide(filter_counter));

                    if filter_counter < (4 + 2 * filter_order) then
                        filter_counter <= filter_counter + 1;
                    else
                        filtered_value <= sum;
                        filter_counter <= 0;
                    end if;

                when NORMALIZE_RESULT =>

                    if S(0) = '0' then

                        normalized := shift_right(filtered_value, 4) +
                                      shift_right(filtered_value, 6) +
                                      shift_right(filtered_value, 8) +
                                      shift_right(filtered_value, 10);

                        -- NOTE: Correct + 4 for vhdl rounding
                        if normalized < 0 then 
                            normalized := normalized + 4;
                        end if;

                    else

                        normalized := shift_right(filtered_value, 6) + 
                                      shift_right(filtered_value, 10);

                        -- NOTE: Correct +2 for vhdl rounding
                        if normalized < 0 then 
                            normalized := normalized + 2;
                        end if;

                    end if;

                    temp_result <= normalized;

                when SATURATE_RESULT =>
                    if temp_result > 127 then
                        data_buffer <= "01111111";
                    elsif temp_result < -128 then
                        data_buffer <= "10000000";
                    else
                        data_buffer <= std_logic_vector(temp_result(7 downto 0));
                    end if;

                when WRITE_OUTPUT =>
                    if data_counter < K then
                        data_counter <= data_counter + 1;
                    else
                        data_counter <= (others => '0');
                    end if;

                when WRITE_WAIT =>
                    null;

                when SLIDE_WINDOW =>
                    null;

                when SLIDE_WAIT =>

                    if S(0) = '0' then
                        for i in 0 to 3 loop
                            input_slide(i) <= input_slide(i + 1);
                        end loop;

                        if (to_integer(data_counter) + 2 < to_integer(K)) then
                            input_slide(4) <= i_mem_data;
                        else
                            -- End of array, pad with zero
                            input_slide(4) <= (others => '0');
                        end if;

                    else

                        for i in 0 to 5 loop
                            input_slide(i) <= input_slide(i + 1);
                        end loop;

                        if (to_integer(data_counter) + 3 < to_integer(K)) then
                            input_slide(6) <= i_mem_data;
                        else
                            -- End of array, pad with zero
                            input_slide(6) <= (others => '0');
                        end if;

                    end if;

                    -- WARN: Can be shortened

                when DONE_STATE =>
                    null;

            end case;
        end if;
    end process;

    -- Next state logic 
    state_transition: process(current_state, i_start, K, S, filter_counter, filter_order, data_counter, header_counter, init_counter)
    begin
        case current_state is
            when IDLE =>
                if i_start = '1' then
                    next_state <= READ_HEADER;
                else 
                    next_state <= IDLE;
                end if;

            when READ_HEADER =>
                next_state <= READ_HD_WAIT;

            when READ_HD_WAIT => 
                if header_counter = 16 then
                    next_state <= INIT_WINDOW;
                else
                    next_state <= READ_HEADER;
                end if;

            when INIT_WINDOW =>
                next_state <= INIT_WAIT;

            when INIT_WAIT => 
                if init_counter = (2 + filter_order) then
                    next_state <= APPLY_FILTER;
                else
                    next_state <= INIT_WINDOW;
                end if;

            when APPLY_FILTER => 
                if filter_counter = (4 + 2 * filter_order) then
                    next_state <= NORMALIZE_RESULT;
                else 
                    next_state <= APPLY_FILTER;
                end if;

            when NORMALIZE_RESULT => 
                next_state <= SATURATE_RESULT;

            when SATURATE_RESULT =>
                next_state <= WRITE_OUTPUT;

            when WRITE_OUTPUT =>
                next_state <= WRITE_WAIT;

            when WRITE_WAIT =>
                if data_counter = K then
                    next_state <= DONE_STATE;
               else
                    next_state <= SLIDE_WINDOW;
                end if;

            when SLIDE_WINDOW =>
                next_state <= SLIDE_WAIT;

            when SLIDE_WAIT =>
                next_state <= APPLY_FILTER;

            when DONE_STATE =>
                if i_start = '0' then
                    next_state <= IDLE;
                else
                    next_state <= DONE_STATE;
                end if;

            when others =>
                next_state <= IDLE;
        end case;
    end process;

    output_logic: process(current_state, base_address, header_counter, init_counter, K, data_counter, data_buffer, filter_order)
    begin
        -- Default outputs
        o_done <= '0';
        o_mem_en <= '0';
        o_mem_we <= '0';
        o_mem_addr <= (others => '0');
        o_mem_data <= (others => '0');

        case current_state is
            when IDLE =>
                null;

            when READ_HEADER =>
                o_mem_en <= '1';
                o_mem_we <= '0';
                o_mem_addr <= std_logic_vector(unsigned(base_address) + header_counter);

            when READ_HD_WAIT => 
                o_mem_en <= '0'; 

            when INIT_WINDOW =>
                o_mem_en <= '1';
                o_mem_we <= '0';

                if init_counter < 3 + filter_order then
                    o_mem_addr <= std_logic_vector(unsigned(base_address) + 17 + init_counter);
                end if;

            when INIT_WAIT =>
                o_mem_en <= '0';

            when WRITE_OUTPUT =>
                o_mem_en <= '1';
                o_mem_we <= '1';
                o_mem_addr <= std_logic_vector(unsigned(base_address) + 17 + K + data_counter);
                o_mem_data <= data_buffer;

            when WRITE_WAIT =>
                o_mem_en <= '0';
                o_mem_we <= '0';

            when SLIDE_WINDOW =>
                o_mem_en <= '1';
                o_mem_we <= '0';

                if (to_integer(data_counter) + 2 + filter_order < to_integer(K)) then
                    o_mem_addr <= std_logic_vector(unsigned(base_address) + 17 + to_integer(data_counter) + 2 + filter_order);
                else
                    -- No memory read needed for padding
                    o_mem_en <= '0';
                end if;

            when SLIDE_WAIT =>
                o_mem_en <= '0'; 

            when DONE_STATE =>
                o_done <= '1';
                o_mem_en <= '0';

            when others =>
                null;
        end case;
    end process;
end Behavioral;
