import java.io.*;
import java.util.*;


public class json_parser {
  String text = "";
  //int first;
  //int last;
  Vector elements = new Vector();
  public int element_index=0;

  json_parser(String text) {
    this.text = text;
    elements = new Vector();
  }


  class json_element {
    public static final int JSON_VAL_UNDEF=-1;
    public static final int JSON_VAL_NULL=0;
    public static final int JSON_VAL_TRUE=1;
    public static final int JSON_VAL_FALSE=2;
    public static final int JSON_VAL_NUMBER=3;
    public static final int JSON_VAL_STRING=4;
    public static final int JSON_VAL_ARRAY=5;
    public static final int JSON_VAL_OBJECT=6;
    public static final int JSON_VAL_KEYVAL=7;
    int type  = JSON_VAL_UNDEF;
    int start = 0;
    int end   = 0;
    int depth = 0;
    public json_element(int what, int start, int end, int depth) {
      this.type = what;
      this.start = start;
      this.end = end;
      this.depth = depth;
    }
    public void update_element(int what, int start, int end, int depth) {
      this.type = what;
      this.start = start;
      this.end = end;
      this.depth = depth;
    }
    public String get_type () {
      if (type == JSON_VAL_UNDEF) return ( "Undefined" );
      if (type == JSON_VAL_NULL) return ( "NULL" );
      if (type == JSON_VAL_TRUE) return ( "True" );
      if (type == JSON_VAL_FALSE) return ( "False" );
      if (type == JSON_VAL_NUMBER) return ( "Number" );
      if (type == JSON_VAL_STRING) return ( "String" );
      if (type == JSON_VAL_ARRAY) return ( "Array" );
      if (type == JSON_VAL_OBJECT) return ( "Object" );
      if (type == JSON_VAL_KEYVAL) return ( "Key:Val" );
      return ( "Unknown" );
    }
  }


  json_element pre_store_skipped ( int what, int start, int end, int depth ) {
    json_element je = new json_element ( what, start, end, depth );
    elements.addElement(je);
    //System.out.println ( "Pre-Skipped " + what + " at depth " + depth + " from " + start + " to " + end );
    return je;
  }

  void post_store_skipped ( int what, int start, int end, int depth ) {
    json_element je = new json_element ( what, start, end, depth );
    elements.addElement(je);
    //System.out.println ( "Post-Skipped " + what + " at depth " + depth + " from " + start + " to " + end );
  }

  void post_store_skipped ( int what, int start, int end, int depth, json_element je ) {
    // json_element je = new json_element ( what, start, end, depth );
    // elements.addElement(je);
    je.update_element ( what, start, end, depth );
    //System.out.println ( "Post-Skipped " + what + " at depth " + depth + " from " + start + " to " + end );
  }

  public void dump ( int max_len ) {
    json_element j;
    for (int i=0; i<elements.size(); i++) {
      j = (json_element)(elements.elementAt(i));
      // System.out.println ( "E[" + i + "] is a " + j.get_type() + " at depth " + j.depth + " from " + j.start + " to " + (j.end-1) );
      for (int d=0; d<j.depth; d++) {
        System.out.print ( "    " );
      }
      String display;
      if ( (j.end - j.start) <= max_len ) {
        display = text.substring(j.start,j.end);
      } else {
        display = text.substring(j.start,j.start+max_len-4) + " ... " + text.substring(j.end-20,j.end);
      }
      System.out.println ( "|-" + j.get_type() + " at depth " + j.depth + " from " + j.start + " to " + (j.end-1) + " = " + display );
    }
  }

  public Object convert_to_object_tree ( Object parent ) {
    if (element_index < elements.size()) {
      json_element j, jj;
      j = (json_element)(elements.elementAt(element_index++));

      //for (int d=0; d<j.depth; d++) { System.out.print ( "    " ); }
      //System.out.println ( "|-" + j.get_type() + " at depth " + j.depth + " from " + j.start + " to " + (j.end-1) );

      if (j.type == json_element.JSON_VAL_ARRAY) {

        // Make and fill a list
        ArrayList<Object> obj_list = new ArrayList<Object>();
        if (element_index < elements.size()) {
          jj = (json_element)(elements.elementAt(element_index));
          while (jj.depth > j.depth) {
            Object child = convert_to_object_tree ( j );
            obj_list.add ( child );
            if (element_index < elements.size()) {
              jj = (json_element)(elements.elementAt(element_index));
            } else {
              break;
            }
          }
        }
        return ( obj_list );

      } else if (j.type == json_element.JSON_VAL_OBJECT) {

        // Make and fill a dictionary
        HashMap<String,Object> obj_dict = new HashMap<String,Object>();

        if (element_index < elements.size()) {
          jj = (json_element)(elements.elementAt(element_index));
          while (jj.depth > j.depth) {
            if (jj.type == json_element.JSON_VAL_KEYVAL) {
              json_element key_element = (json_element)(elements.elementAt(element_index + 1));
              json_element val_element = (json_element)(elements.elementAt(element_index + 2));
              String key = text.substring(key_element.start,key_element.end);
              element_index += 2;
              Object child = convert_to_object_tree ( val_element );
              obj_dict.put ( key, child );
              if (element_index < elements.size()) {
                jj = (json_element)(elements.elementAt(element_index));
              } else {
                break;
              }
            } else {
              System.out.println ( "All elements in a dictionary must be key-val pairs" );
              System.exit(10);
            }
          }
        }

        return obj_dict;


      } else if (j.type == json_element.JSON_VAL_KEYVAL) {

        // Add key value to parent dictionary
        return ( "KV-Pair" );

      } else if (j.type == json_element.JSON_VAL_STRING) {
        // Make and return a string
        return ( text.substring(j.start,j.end) );
      } else if (j.type == json_element.JSON_VAL_NUMBER) {
        try {
          return ( Integer.parseInt(text.substring(j.start,j.end)) );
        } catch (NumberFormatException nfe) {
          return ( Double.parseDouble(text.substring(j.start,j.end)) );
        }
      } else if (j.type == json_element.JSON_VAL_NULL) {
        return ( null );
      } else if (j.type == json_element.JSON_VAL_TRUE) {
        return ( true );
      } else if (j.type == json_element.JSON_VAL_FALSE) {
        return ( false );
      } else if (j.type == json_element.JSON_VAL_UNDEF) {
        return ( null );
      } else {
        return ( null );
      }
    }
    return null;
  }

  public Object generate_object_tree () {
	  skip_element ( 0, 0 );
	  // p.dump(70);
	  // Set the first element to 0
	  element_index = 0;
	  // Convert the text into an actual object tree (usually a List or a HashMap)
	  Object o = convert_to_object_tree( null );
	  // Return the object tree
	  return ( o );
  }

  int skip_whitespace ( int index, int depth ) {
    int i = index;
    int max = text.length();
    while ( Character.isWhitespace(text.charAt(i)) ) {
      i++;
      if (i >= max) {
        return ( -1 );
      }
    }
    // post_store_skipped ( json_element.JSON_VAL_UNDEF, index, i, depth );
    return i;
  }

  int skip_sepspace ( int index, int depth ) {
    int i = index;
    int max = text.length();
    while ( (text.charAt(i)==',') || Character.isWhitespace(text.charAt(i)) ) {
      i++;
      if (i >= max) {
        return ( -1 );
      }
    }
    // post_store_skipped ( json_element.JSON_VAL_UNDEF, index, i, depth );
    return i;
  }

  int skip_element ( int index, int depth ) {
    int start = skip_whitespace ( index, depth );
    if (start >= 0) {
      if ( text.charAt(start) == '{' ) {
        start = skip_object ( start, depth );
      } else if ( text.charAt(start) == '[' ) {
        start = skip_array ( start, depth );
      } else if ( text.charAt(start) == '\"' ) {
        start = skip_string ( start, depth );
      } else if ( (new String("-0123456789")).indexOf(text.charAt(start)) >= 0 ) {
        start = skip_number ( start, depth );
      } else if ( (new String("null")).regionMatches(0,text,start,4) ) {
        post_store_skipped ( json_element.JSON_VAL_NULL, start, start+4, depth );
        start += 4;
      } else if ( (new String("true")).regionMatches(0,text,start,4) ) {
        post_store_skipped ( json_element.JSON_VAL_TRUE, start, start+4, depth );
        start += 4;
      } else if ( (new String("false")).regionMatches(0,text,start,5) ) {
        post_store_skipped ( json_element.JSON_VAL_FALSE, start, start+5, depth );
        start += 5;
      } else {
        int lead = Math.max(0,start-10);
        int trail = Math.min(start+10,text.length()-1);
        System.out.println ( "Unexpected char (\"" + text.charAt(start) + "\") in JSON: \"" + text.substring(lead,trail) + "\"" );
        System.exit(12);
      }
    }
    return start;
  }

  int skip_keyval ( int index, int depth ) {
    json_element je = pre_store_skipped ( json_element.JSON_VAL_KEYVAL, index, index, depth );
    index = skip_whitespace ( index, depth );
    int end = index;
    end = skip_string ( end, depth );
    end = skip_whitespace ( end, depth );
    end = end + 1;  // This is the colon separator (:)
    end = skip_element ( end, depth );
    post_store_skipped ( json_element.JSON_VAL_KEYVAL, index, end, depth, je );
    return (end);
  }

  int skip_object ( int index, int depth ) {
    json_element je = pre_store_skipped ( json_element.JSON_VAL_OBJECT, index, index, depth );
    int end = index+1;
    depth += 1;
    while (text.charAt(end) != '}') {
      end = skip_keyval ( end, depth );
      end = skip_sepspace ( end, depth );
    }
    depth += -1;
    post_store_skipped ( json_element.JSON_VAL_OBJECT, index, end+1, depth, je );
    return (end + 1);
  }

  int skip_array ( int index, int depth ) {
    json_element je = pre_store_skipped ( json_element.JSON_VAL_ARRAY, index, index, depth );
    int end = index+1;
    depth += 1;
    while (text.charAt(end) != ']') {
      end = skip_element ( end, depth );
      end = skip_sepspace ( end, depth );
    }
    depth += -1;
    post_store_skipped ( json_element.JSON_VAL_ARRAY, index, end+1, depth, je );
    return (end + 1);
  }

  int skip_string ( int index, int depth ) {
    int end = index+1;
    while (text.charAt(end) != '"') {
      end++;
    }
    //post_store_skipped ( json_element.JSON_VAL_STRING, index, end+1, depth );  // Store the quotation marks
    post_store_skipped ( json_element.JSON_VAL_STRING, index+1, end, depth );    // Don't store the quotation marks
    return (end + 1);
  }

  int skip_number ( int index, int depth ) {
    int end = index;
    String number_chars = "0123456789.-+eE";
    while (number_chars.indexOf(text.charAt(end)) >= 0 ) {
      end++;
    }
    post_store_skipped ( json_element.JSON_VAL_NUMBER, index, end, depth );
    return (end);
  }

	public static void main ( String args[] ) throws Exception {

	  System.out.println ( "JSON Parser" );

	  String text;

	  //text = "{ \"key\" : \"val\" }";
	  //text = "[ [], {}, true, false, null, 5, -2, 0, 0.3, -3e-7, 2e2, \"Abc\" ]";
	  //text = "[ [], [1,2,\"x\", \"y\"], {}, true, false, null, 5, -2, 0, 0.3, -3e-7, 2e2, \"Abc\" ]";
	  //text = "\"a\"";
	  //text = "[ \"a\", -1, 0, -1.5, 1.5, [\"b\", \"c\"], [], \"d\", {\"a\":3,\"b\":30}, \"e\" ]";
	  text = " { \"D\": {\"d1\":1,\"d2\":2}, \"L\" : [ 2, -1, {\"a\":1,\"b\":2,\"c\":3}, { \"mc\":[ { \"a\":0 }, 2, true, [9,[0,3],\"a\",3], false, null, 5, [1,2,3], \"xyz\" ], \"x\":\"y\" }, -3, 7 ] }  ";
	  //text = " { \"ALL\" : [\n 2, -1, {\"a\":1,\"b\":2,\"c\":3},\n { \"mc\":[ { \"a\":0 },\n 2, true, [9,[0,3],\"a\",3],\n false, null, 5, [1,2,3], \"xyz\" ],\n \"x\":\"y\" }, -3, 7 ] }  ";
	  //text = "[ 1,2,3, {\"mc\":[{\"a\":0},2,true,[9,[0.,3],\"a\",3],false,null,5,[1,2.0,0.3],\"xyz\"],\"x\":\"y\",\"y\":33}  ]";
	  //text = "{\"mcell\": {\"blender_version\": [2, 68, 0], \"api_version\": 0, \"reaction_data_output\": {\"mol_colors\": false, \"reaction_output_list\": [], \"plot_legend\": \"0\", \"combine_seeds\": true, \"plot_layout\": \" plot \"}, \"define_molecules\": {\"molecule_list\": [{\"export_viz\": false, \"diffusion_constant\": \"1e-7\", \"data_model_version\": \"DM_2014_10_24_1638\", \"custom_space_step\": \"\", \"maximum_step_length\": \"\", \"mol_name\": \"a\", \"mol_type\": \"3D\", \"custom_time_step\": \"\", \"target_only\": false}, {\"export_viz\": false, \"diffusion_constant\": \"1e-7\", \"data_model_version\": \"DM_2014_10_24_1638\", \"custom_space_step\": \"\", \"maximum_step_length\": \"\", \"mol_name\": \"b\", \"mol_type\": \"3D\", \"custom_time_step\": \"\", \"target_only\": false}], \"data_model_version\": \"DM_2014_10_24_1638\"}, \"define_reactions\": {\"reaction_list\": []}, \"data_model_version\": \"DM_2014_10_24_1638\", \"define_surface_classes\": {\"surface_class_list\": []}, \"parameter_system\": {\"model_parameters\": []}, \"define_release_patterns\": {\"release_pattern_list\": []}, \"release_sites\": {\"release_site_list\": [{\"object_expr\": \"\", \"location_x\": \"0\", \"location_y\": \"0\", \"release_probability\": \"1\", \"stddev\": \"0\", \"quantity\": \"100\", \"pattern\": \"\", \"site_diameter\": \"0\", \"orient\": \"'\", \"name\": \"ra\", \"shape\": \"CUBIC\", \"quantity_type\": \"NUMBER_TO_RELEASE\", \"molecule\": \"a\", \"location_z\": \"0\"}, {\"object_expr\": \"\", \"location_x\": \"0\", \"location_y\": \".2\", \"release_probability\": \"1\", \"stddev\": \"0\", \"quantity\": \"100\", \"pattern\": \"\", \"site_diameter\": \"0\", \"orient\": \"'\", \"name\": \"rb\", \"shape\": \"CUBIC\", \"quantity_type\": \"NUMBER_TO_RELEASE\", \"molecule\": \"b\", \"location_z\": \"0\"}]}, \"modify_surface_regions\": {\"modify_surface_regions_list\": []}, \"initialization\": {\"center_molecules_on_grid\": false, \"iterations\": \"10\", \"warnings\": {\"missing_surface_orientation\": \"ERROR\", \"high_probability_threshold\": \"1.0\", \"negative_diffusion_constant\": \"WARNING\", \"degenerate_polygons\": \"WARNING\", \"lifetime_too_short\": \"WARNING\", \"negative_reaction_rate\": \"WARNING\", \"high_reaction_probability\": \"IGNORED\", \"missed_reactions\": \"WARNING\", \"lifetime_threshold\": \"50\", \"useless_volume_orientation\": \"WARNING\", \"missed_reaction_threshold\": \"0.0010000000474974513\", \"all_warnings\": \"INDIVIDUAL\"}, \"space_step\": \"\", \"radial_directions\": \"\", \"radial_subdivisions\": \"\", \"vacancy_search_distance\": \"\", \"time_step_max\": \"\", \"accurate_3d_reactions\": true, \"notifications\": {\"probability_report_threshold\": \"0.0\", \"varying_probability_report\": true, \"probability_report\": \"ON\", \"iteration_report\": true, \"progress_report\": true, \"molecule_collision_report\": false, \"box_triangulation_report\": false, \"release_event_report\": true, \"file_output_report\": false, \"partition_location_report\": false, \"all_notifications\": \"INDIVIDUAL\", \"diffusion_constant_report\": \"BRIEF\", \"final_summary\": true}, \"time_step\": \"5e-6\", \"interaction_radius\": \"\", \"surface_grid_density\": \"10000\", \"microscopic_reversibility\": \"OFF\", \"partitions\": {\"x_start\": \"-1.0\", \"x_step\": \"0.019999999552965164\", \"y_step\": \"0.019999999552965164\", \"y_end\": \"1.0\", \"recursion_flag\": false, \"z_end\": \"1.0\", \"x_end\": \"1.0\", \"z_step\": \"0.019999999552965164\", \"include\": false, \"y_start\": \"-1.0\"}}, \"model_objects\": {\"model_object_list\": [{\"name\": \"Cube\"}]}, \"geometrical_objects\": {\"object_list\": [{\"element_connections\": [[4, 5, 0], [5, 6, 1], [6, 7, 2], [7, 4, 3], [0, 1, 3], [7, 6, 4], [6, 2, 1], [6, 5, 4], [5, 1, 0], [7, 3, 2], [1, 2, 3], [4, 0, 3]], \"name\": \"Cube\", \"vertex_list\": [[-0.25, -0.25, -0.25], [-0.25, 0.25, -0.25], [0.25, 0.25, -0.25], [0.25, -0.25, -0.25], [-0.25, -0.25, 0.25], [-0.25, 0.25, 0.25], [0.25, 0.25, 0.25], [0.25, -0.25, 0.25]], \"location\": [0.0, 0.0, 0.0]}]}, \"viz_output\": {\"all_iterations\": true, \"step\": \"1\", \"end\": \"1\", \"export_all\": true, \"start\": \"0\"}, \"materials\": {\"material_dict\": {}}, \"cellblender_version\": \"0.1.54\", \"cellblender_source_sha1\": \"6a572dab58fa0f770c46ce3ac26b01f3a66f2096\"}}";
		// BufferedReader f = new BufferedReader ( new InputStreamReader ( new FileInputStream ( "dm.json" ) ) );

	  /*
	  if (text.indexOf('\n') < 0) {
	    System.out.println ( "Text = " + text );
	    System.out.println ( "      01234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890" );
	    System.out.println ( "      0         1         2         3         4         5         6         7         8         9         0         1         2         3         4         5         6" );
	  }
	  */
    System.out.println ( "Text = " + text );

	  json_parser p = new json_parser( text );
	  Object o = p.generate_object_tree();

	  System.out.println ( "Object = " + o );

	}

}
